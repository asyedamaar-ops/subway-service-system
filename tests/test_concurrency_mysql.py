"""Concurrency tests that need real row locks, so they run on MySQL or MariaDB only.

    TEST_DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/subway_test pytest

SQLite ignores SELECT ... FOR UPDATE, so these tests are skipped without that
variable. The database named in the URL is wiped by the tests.
"""
import os
import threading

import pytest

from app import db
from app.models import Booking, BookingStatus, User, Waitlist
from app.services.booking import book_seat, cancel_booking
from tests.conftest import add_schedule, add_user, make_app

MYSQL_URL = os.environ.get('TEST_DATABASE_URL', '')
pytestmark = pytest.mark.skipif(not MYSQL_URL.startswith('mysql'),
                                reason='set TEST_DATABASE_URL to a MySQL/MariaDB database')

REQUESTS = 12


@pytest.fixture
def mysql_app():
    app = make_app(SQLALCHEMY_DATABASE_URI=MYSQL_URL, SQLALCHEMY_ENGINE_OPTIONS={'pool_size': REQUESTS + 2})
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def run_together(app, jobs):
    """Run every job in its own thread and database session, all released at the same moment."""
    db.session.remove()      # the main thread must not keep an old snapshot or locks
    barrier = threading.Barrier(len(jobs))
    results, errors = [None] * len(jobs), []

    def worker(index, job):
        with app.app_context():
            try:
                # A request loads the logged-in user before it books. That plain read starts
                # the transaction snapshot BEFORE the lock is taken, which is the hard case.
                db.session.query(User).first()
                barrier.wait(timeout=20)
                results[index] = job()
            except Exception as exc:      # collected and re-raised in the main thread
                errors.append(exc)
            finally:
                db.session.remove()

    threads = [threading.Thread(target=worker, args=(i, job)) for i, job in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    db.session.remove()      # so the checks below read what the threads committed
    return results


def test_last_seat_is_sold_exactly_once(mysql_app):
    passenger_ids = [add_user(f'p{i}').passengers.passenger_id for i in range(REQUESTS)]
    sid = add_schedule(economy=1).schedule_id          # ONE economy seat, 12 buyers

    results = run_together(mysql_app, [
        (lambda pid=pid: book_seat(pid, sid, 'economy').waitlist_position) for pid in passenger_ids
    ])

    confirmed = Booking.query.filter_by(schedule_id=sid, seat_type='economy',
                                        status=BookingStatus.confirmed).count()
    positions = sorted(w.position for w in Waitlist.query.filter_by(schedule_id=sid, seat_type='economy'))
    assert confirmed == 1
    assert results.count(None) == 1                                  # one request got the seat
    assert positions == list(range(1, REQUESTS))                     # the rest queue up as 1..11, no gaps or repeats


def test_seats_fill_up_to_capacity_and_no_further(mysql_app):
    passenger_ids = [add_user(f'p{i}').passengers.passenger_id for i in range(REQUESTS)]
    sid = add_schedule(economy=5).schedule_id

    run_together(mysql_app, [(lambda pid=pid: book_seat(pid, sid, 'economy')) for pid in passenger_ids])

    seats = sorted(b.seat_number for b in Booking.query.filter_by(schedule_id=sid, status=BookingStatus.confirmed))
    assert seats == ['E1', 'E2', 'E3', 'E4', 'E5']                   # five different seats
    assert Waitlist.query.filter_by(schedule_id=sid).count() == REQUESTS - 5


def test_simultaneous_cancel_requests_promote_one_passenger(mysql_app):
    p1, p2, p3 = [add_user(f'p{i}').passengers.passenger_id for i in range(3)]
    sid = add_schedule(business=1).schedule_id
    held = book_seat(p1, sid, 'business').booking.booking_id
    book_seat(p2, sid, 'business')
    book_seat(p3, sid, 'business')

    results = run_together(mysql_app, [(lambda: cancel_booking(held).cancelled) for _ in range(6)])

    assert results.count(True) == 1                                  # only one request did the cancel
    confirmed = Booking.query.filter_by(schedule_id=sid, seat_type='business', status=BookingStatus.confirmed).all()
    assert [b.passenger_id for b in confirmed] == [p2]
    assert [(w.passenger_id, w.position) for w in Waitlist.query.filter_by(schedule_id=sid)] == [(p3, 1)]


def test_cancel_and_new_bookings_at_the_same_time_never_oversell(mysql_app):
    passenger_ids = [add_user(f'p{i}').passengers.passenger_id for i in range(REQUESTS)]
    sid = add_schedule(economy=2).schedule_id
    first = book_seat(passenger_ids[0], sid, 'economy').booking.booking_id
    book_seat(passenger_ids[1], sid, 'economy')

    jobs = [lambda: cancel_booking(first)]
    jobs += [(lambda pid=pid: book_seat(pid, sid, 'economy')) for pid in passenger_ids[2:]]
    run_together(mysql_app, jobs)

    seats = sorted(b.seat_number for b in Booking.query.filter_by(schedule_id=sid, status=BookingStatus.confirmed))
    assert seats == ['E1', 'E2']                                     # both seats sold, each once
    positions = sorted(w.position for w in Waitlist.query.filter_by(schedule_id=sid))
    assert positions == list(range(1, len(positions) + 1))
