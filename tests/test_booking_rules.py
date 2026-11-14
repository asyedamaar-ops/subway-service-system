"""Seat allocation, waitlist and cancellation rules (app/services/booking.py)."""
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.clock import local_today
from app.models import Booking, BookingStatus, Waitlist
from app.services.booking import BookingError, book_seat, cancel_booking
from tests.conftest import add_schedule


def confirmed(schedule_id, seat_type):
    return Booking.query.filter_by(schedule_id=schedule_id, seat_type=seat_type,
                                   status=BookingStatus.confirmed).all()


def queue(schedule_id, seat_type):
    rows = Waitlist.query.filter_by(schedule_id=schedule_id, seat_type=seat_type).order_by(Waitlist.position).all()
    return [(w.passenger_id, w.position) for w in rows]


def test_booking_takes_the_lowest_free_seat(passengers, schedule):
    p1, p2, *_ = passengers
    first = book_seat(p1, schedule.schedule_id, 'economy')
    second = book_seat(p2, schedule.schedule_id, 'economy')

    assert not first.waitlisted and not second.waitlisted
    assert [first.booking.seat_number, second.booking.seat_number] == ['E1', 'E2']
    assert float(first.booking.total_fare) == schedule.fare_for('economy')


def test_full_class_goes_to_the_waitlist_in_arrival_order(passengers, schedule):
    p1, p2, p3, p4 = passengers
    sid = schedule.schedule_id
    book_seat(p1, sid, 'economy')
    book_seat(p2, sid, 'economy')          # economy has 2 seats, now full

    third = book_seat(p3, sid, 'economy')
    fourth = book_seat(p4, sid, 'economy')

    assert third.waitlisted and third.waitlist_position == 1
    assert fourth.waitlisted and fourth.waitlist_position == 2
    assert len(confirmed(sid, 'economy')) == 2          # never more than the capacity
    assert queue(sid, 'economy') == [(p3, 1), (p4, 2)]


def test_same_passenger_is_not_waitlisted_twice(passengers, schedule):
    p1, p2, *_ = passengers
    sid = schedule.schedule_id
    book_seat(p1, sid, 'business')                       # business has 1 seat

    assert book_seat(p2, sid, 'business').waitlist_position == 1
    assert book_seat(p2, sid, 'business').waitlist_position == 1
    assert queue(sid, 'business') == [(p2, 1)]


def test_cancel_promotes_the_first_waiting_passenger(passengers, schedule):
    p1, p2, p3, _ = passengers
    sid = schedule.schedule_id
    held = book_seat(p1, sid, 'business').booking
    book_seat(p2, sid, 'business')
    book_seat(p3, sid, 'business')

    result = cancel_booking(held.booking_id)

    assert result.cancelled
    assert result.promoted.passenger_id == p2            # first in, first out
    assert result.promoted.seat_number == 'B1'           # the freed seat is reused
    assert result.promoted.payment_method == 'waitlist_promoted'
    assert [b.passenger_id for b in confirmed(sid, 'business')] == [p2]
    assert queue(sid, 'business') == [(p3, 1)]           # p3 moved up from 2 to 1


def test_cancelling_twice_promotes_only_one_passenger(passengers, schedule):
    """Regression test: a repeated cancel request used to promote a second passenger."""
    p1, p2, p3, _ = passengers
    sid = schedule.schedule_id
    held = book_seat(p1, sid, 'business').booking
    book_seat(p2, sid, 'business')
    book_seat(p3, sid, 'business')

    first = cancel_booking(held.booking_id)
    second = cancel_booking(held.booking_id)

    assert first.cancelled and first.promoted is not None
    assert not second.cancelled and second.promoted is None
    assert len(confirmed(sid, 'business')) == 1          # still one seat, one booking
    assert queue(sid, 'business') == [(p3, 1)]


def test_cancel_without_waitlist_just_frees_the_seat(passengers, schedule):
    p1, p2, *_ = passengers
    sid = schedule.schedule_id
    held = book_seat(p1, sid, 'premium_economy').booking

    result = cancel_booking(held.booking_id)

    assert result.cancelled and result.promoted is None
    assert book_seat(p2, sid, 'premium_economy').booking.seat_number == 'P1'


def test_no_promotion_while_the_class_is_still_over_capacity(passengers, schedule):
    p1, p2, p3, _ = passengers
    sid = schedule.schedule_id
    a = book_seat(p1, sid, 'economy').booking
    book_seat(p2, sid, 'economy')
    book_seat(p3, sid, 'economy')                        # waitlisted
    schedule.metro.economy_seats = 1                     # admin shrinks the class from 2 to 1
    db.session.commit()

    result = cancel_booking(a.booking_id)

    assert result.cancelled and result.promoted is None  # 1 booking left on 1 seat: no room
    assert queue(sid, 'economy') == [(p3, 1)]


def test_classes_are_counted_separately(passengers, schedule):
    p1, p2, *_ = passengers
    sid = schedule.schedule_id
    book_seat(p1, sid, 'business')
    other = book_seat(p2, sid, 'premium_economy')
    assert not other.waitlisted and other.booking.seat_number == 'P1'


def test_unknown_seat_class_and_payment_method_are_rejected(passengers, schedule):
    with pytest.raises(BookingError):
        book_seat(passengers[0], schedule.schedule_id, 'first_class')
    with pytest.raises(BookingError):
        book_seat(passengers[0], schedule.schedule_id, 'economy', 'cash')
    assert Booking.query.count() == 0


def test_departed_or_inactive_train_cannot_be_booked(passengers, schedule):
    yesterday = add_schedule(days_ahead=-1)
    with pytest.raises(BookingError):
        book_seat(passengers[0], yesterday.schedule_id, 'economy')

    schedule.is_active = False
    db.session.commit()
    with pytest.raises(BookingError):
        book_seat(passengers[0], schedule.schedule_id, 'economy')

    with pytest.raises(BookingError):
        book_seat(passengers[0], 99999, 'economy')       # no such train


def test_database_refuses_two_confirmed_bookings_on_one_seat(passengers, schedule):
    """The unique index on (schedule_id, active_seat) is the last line of defence."""
    p1, p2, *_ = passengers
    first = book_seat(p1, schedule.schedule_id, 'economy').booking

    clash = Booking(passenger_id=p2, schedule_id=schedule.schedule_id, ticket_no='TKT-CLASH',
                    seat_type='economy', seat_number=first.seat_number, total_fare=100)
    db.session.add(clash)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    # once the first booking is cancelled the same seat number is allowed again
    cancel_booking(first.booking_id)
    db.session.add(Booking(passenger_id=p2, schedule_id=schedule.schedule_id, ticket_no='TKT-OK',
                           seat_type='economy', seat_number='E1', total_fare=100))
    db.session.commit()


def test_schedule_is_bookable_only_before_departure(schedule):
    assert schedule.is_bookable()
    assert schedule.travel_date > local_today() - timedelta(days=1)
    assert not add_schedule(days_ahead=-2).is_bookable()
