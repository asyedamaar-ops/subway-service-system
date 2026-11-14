"""Booking rules: seat allocation, waitlisting, cancellation and waitlist promotion.

How overselling is prevented
----------------------------
Every function here does its work in ONE database transaction and starts by
locking the schedule row with SELECT ... FOR UPDATE. Two requests for the same
train therefore run one after the other, never at the same time.

The seat count and the waitlist are also read with FOR UPDATE. A locking read
always returns the latest committed rows. A plain SELECT inside a MySQL
transaction can return an older snapshot, which is exactly how two people
could both see "1 seat left".

The routes in app/routes/booking.py stay thin and call these functions.
"""
import secrets
import string
from dataclasses import dataclass
from typing import Optional

from app import db
from app.models import Booking, BookingStatus, Schedule, Waitlist, SEAT_PREFIX

PAYMENT_METHODS = ('upi', 'card', 'netbanking')
_CODE_CHARS = string.ascii_uppercase + string.digits


class BookingError(Exception):
    """A booking rule was broken. The message is safe to show to the user."""


@dataclass
class BookingResult:
    booking: Optional[Booking] = None          # set when a seat was confirmed
    waitlist_position: Optional[int] = None    # set when the class was full

    @property
    def waitlisted(self):
        return self.booking is None


@dataclass
class CancelResult:
    cancelled: bool                            # False if it was already cancelled
    promoted: Optional[Booking] = None         # booking created for the first waitlisted passenger


def _code(prefix, length):
    return prefix + ''.join(secrets.choice(_CODE_CHARS) for _ in range(length))


def _lock_schedule(schedule_id):
    """Lock the schedule row until this transaction commits or rolls back."""
    return (
        db.session.query(Schedule)
        .filter(Schedule.schedule_id == schedule_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )


def _confirmed_seats(schedule_id, seat_type):
    """Seat numbers of the confirmed bookings in one class (locking read)."""
    rows = (
        db.session.query(Booking.seat_number)
        .filter(
            Booking.schedule_id == schedule_id,
            Booking.seat_type == seat_type,
            Booking.status == BookingStatus.confirmed,
        )
        .with_for_update()
        .all()
    )
    return [row[0] for row in rows]


def _waiting_queue(schedule_id, seat_type):
    """Waitlist entries of one class in queue order (locking read)."""
    return (
        db.session.query(Waitlist)
        .filter(Waitlist.schedule_id == schedule_id, Waitlist.seat_type == seat_type)
        .order_by(Waitlist.position, Waitlist.waitlist_id)
        .populate_existing()
        .with_for_update()
        .all()
    )


def _first_free_seat(seat_type, capacity, taken):
    """Lowest seat number in the class that no confirmed booking holds."""
    prefix = SEAT_PREFIX[seat_type]
    taken = set(taken)
    for number in range(1, capacity + 1):
        label = f'{prefix}{number}'
        if label not in taken:
            return label
    return None


def _new_booking(passenger_id, schedule, seat_type, seat_number, payment_method):
    return Booking(
        passenger_id=passenger_id,
        schedule_id=schedule.schedule_id,
        ticket_no=_code('TKT-', 10),
        seat_type=seat_type,
        seat_number=seat_number,
        total_fare=schedule.fare_for(seat_type),
        status=BookingStatus.confirmed,
        payment_method=payment_method,
        transaction_id=_code('TXN-', 12),
    )


def _join_waitlist(passenger_id, schedule_id, seat_type):
    """Put the passenger at the end of the queue. Returns the position."""
    queue = _waiting_queue(schedule_id, seat_type)
    for entry in queue:
        if entry.passenger_id == passenger_id:
            return entry.position      # already waiting, keep the old place

    position = len(queue) + 1
    db.session.add(Waitlist(
        passenger_id=passenger_id,
        schedule_id=schedule_id,
        seat_type=seat_type,
        position=position,
    ))
    return position


def _promote_first_waiting(schedule, seat_type):
    """Give a free seat to the first waitlisted passenger (first in, first out)."""
    queue = _waiting_queue(schedule.schedule_id, seat_type)
    if not queue:
        return None      # nobody waiting, nothing to do

    taken = _confirmed_seats(schedule.schedule_id, seat_type)
    capacity = schedule.capacity_for(seat_type)
    if len(taken) >= capacity:
        return None      # still full, for example the admin reduced the capacity

    first, rest = queue[0], queue[1:]
    promoted = _new_booking(
        first.passenger_id, schedule, seat_type,
        _first_free_seat(seat_type, capacity, taken), 'waitlist_promoted',
    )
    db.session.add(promoted)
    db.session.delete(first)

    # everybody behind moves up one place
    for position, entry in enumerate(rest, start=1):
        entry.position = position
    return promoted


def book_seat(passenger_id, schedule_id, seat_type, payment_method='upi'):
    """Confirm a seat, or put the passenger on the waitlist if the class is full."""
    if seat_type not in SEAT_PREFIX:
        raise BookingError('Unknown seat class.')
    if payment_method not in PAYMENT_METHODS:
        raise BookingError('Unknown payment method.')

    try:
        schedule = _lock_schedule(schedule_id)
        if schedule is None or not schedule.is_active:
            raise BookingError('This train is not available for booking.')
        if schedule.has_departed():
            raise BookingError('This train has already departed.')

        taken = _confirmed_seats(schedule_id, seat_type)
        capacity = schedule.capacity_for(seat_type)

        if len(taken) >= capacity:
            position = _join_waitlist(passenger_id, schedule_id, seat_type)
            db.session.commit()
            return BookingResult(waitlist_position=position)

        booking = _new_booking(
            passenger_id, schedule, seat_type,
            _first_free_seat(seat_type, capacity, taken), payment_method,
        )
        db.session.add(booking)
        db.session.commit()
        return BookingResult(booking=booking)
    except Exception:
        db.session.rollback()      # also releases the row lock
        raise


def cancel_booking(booking_id):
    """Cancel a confirmed booking and promote the first waitlisted passenger.

    Both steps are one transaction: either the seat is freed and handed over,
    or nothing changes. A booking that is already cancelled is left alone, so
    sending the same cancel request twice cannot promote two passengers.
    """
    try:
        booking = db.session.get(Booking, booking_id)
        if booking is None:
            raise BookingError('Booking not found.')

        # same lock order as book_seat (schedule first), so the two cannot deadlock
        schedule = _lock_schedule(booking.schedule_id)

        # read the booking again under the lock: a second cancel request waits
        # above and then sees the status the first one committed
        booking = (
            db.session.query(Booking)
            .filter(Booking.booking_id == booking_id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if booking.status != BookingStatus.confirmed:
            db.session.rollback()
            return CancelResult(cancelled=False)

        booking.status = BookingStatus.cancelled
        db.session.flush()      # the seat is free before the promoted booking is inserted

        promoted = _promote_first_waiting(schedule, booking.seat_type)
        db.session.commit()
        return CancelResult(cancelled=True, promoted=promoted)
    except Exception:
        db.session.rollback()
        raise
