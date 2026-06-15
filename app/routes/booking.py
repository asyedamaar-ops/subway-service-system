from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Booking, Waitlist, Schedule, Passenger, BookingStatus
from datetime import datetime
import random, string

booking_bp = Blueprint('booking', __name__)

# helper to make ticket numbers
def _generate_ticket():
    chars = string.ascii_uppercase + string.digits
    return 'TKT-' + ''.join(random.choices(chars, k=8))

def _generate_txn():
    return 'TXN-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def _generate_seat(seat_type):
    # E for economy, P for premium, B for business
    prefix = {'economy': 'E', 'premium_economy': 'P', 'business': 'B'}.get(seat_type, 'X')
    num = random.randint(1, 60)
    return f"{prefix}{num}"


# TRIGGER 1 - check if seat is available before booking
# basically replicating what the DB trigger does but at app level too
def _trigger_validate_seat(schedule, seat_type):
    avail = schedule.available_seats(seat_type)
    if avail <= 0:
        return False, "No seats available in this class."
    return True, None


# TRIGGER 2 - if train full, add passenger to waitlist automatically
def _trigger_add_to_waitlist(passenger_id, schedule_id, seat_type):
    # check if already in waitlist for this schedule+seat combo
    existing = Waitlist.query.filter_by(
        passenger_id=passenger_id,
        schedule_id=schedule_id,
        seat_type=seat_type
    ).first()
    if existing:
        return existing.position

    # get current max position
    max_pos = db.session.query(db.func.max(Waitlist.position)).filter_by(
        schedule_id=schedule_id,
        seat_type=seat_type
    ).scalar()

    if max_pos is None:
        max_pos = 0

    wl = Waitlist(
        passenger_id=passenger_id,
        schedule_id=schedule_id,
        seat_type=seat_type,
        position=max_pos + 1
    )
    db.session.add(wl)
    db.session.commit()
    print(f"[DEBUG] Added passenger {passenger_id} to waitlist at position {max_pos + 1}")
    return wl.position


# TRIGGER 3 - when booking cancelled, promote first person from waitlist
# took me a while to get the re-numbering logic right lol
def _trigger_promote_waitlist(schedule_id, seat_type):
    wl_entry = Waitlist.query.filter_by(
        schedule_id=schedule_id,
        seat_type=seat_type
    ).order_by(Waitlist.position).first()

    if not wl_entry:
        return  # nobody waiting, nothing to do

    schedule = Schedule.query.get(schedule_id)
    new_booking = Booking(
        passenger_id   = wl_entry.passenger_id,
        schedule_id    = schedule_id,
        ticket_no      = _generate_ticket(),
        seat_type      = seat_type,
        seat_number    = _generate_seat(seat_type),
        total_fare     = schedule.fare_for(seat_type),
        status         = BookingStatus.confirmed,
        payment_method = 'waitlist_promoted',
        transaction_id = _generate_txn()
    )
    db.session.add(new_booking)
    db.session.delete(wl_entry)

    # re-number the waitlist positions after removing top entry
    remaining = Waitlist.query.filter_by(
        schedule_id=schedule_id,
        seat_type=seat_type
    ).order_by(Waitlist.position).all()

    for i, w in enumerate(remaining, start=1):
        w.position = i

    db.session.commit()


@booking_bp.route('/select/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def select(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    passenger = current_user.passengers

    if not passenger:
        flash('Please complete your profile before booking.', 'warning')
        return redirect(url_for('auth.profile'))

    # TODO: maybe add a check here for past dates?

    seat_types = [
        {
            'key': 'economy',
            'label': 'Economy',
            'fare': float(schedule.economy_fare),
            'avail': schedule.available_seats('economy'),
            'icon': '🪑'
        },
        {
            'key': 'premium_economy',
            'label': 'Premium Economy',
            'fare': float(schedule.premium_fare),
            'avail': schedule.available_seats('premium_economy'),
            'icon': '💺'
        },
        {
            'key': 'business',
            'label': 'Business',
            'fare': float(schedule.business_fare),
            'avail': schedule.available_seats('business'),
            'icon': '👑'
        },
    ]
    return render_template('booking/select.html', schedule=schedule, seat_types=seat_types)


@booking_bp.route('/payment/<int:schedule_id>/<seat_type>', methods=['GET', 'POST'])
@login_required
def payment(schedule_id, seat_type):
    schedule = Schedule.query.get_or_404(schedule_id)
    passenger = current_user.passengers
    fare = schedule.fare_for(seat_type)
    avail = schedule.available_seats(seat_type)

    if request.method == 'POST':
        pay_method = request.form.get('pay_method', 'upi')

        # run our seat validation trigger
        ok, err = _trigger_validate_seat(schedule, seat_type)
        if not ok:
            # train is full - add to waitlist instead
            position = _trigger_add_to_waitlist(passenger.passenger_id, schedule_id, seat_type)
            flash(f'This class is now full! You have been added to the waitlist at position #{position}.', 'warning')
            return redirect(url_for('booking.my_bookings'))

        booking = Booking(
            passenger_id   = passenger.passenger_id,
            schedule_id    = schedule_id,
            ticket_no      = _generate_ticket(),
            seat_type      = seat_type,
            seat_number    = _generate_seat(seat_type),
            total_fare     = fare,
            status         = BookingStatus.confirmed,
            payment_method = pay_method,
            transaction_id = _generate_txn()
        )
        db.session.add(booking)
        db.session.commit()

        flash('Booking confirmed! Have a safe journey.', 'success')
        return redirect(url_for('booking.confirmation', booking_id=booking.booking_id))

    return render_template('booking/payment.html',
                           schedule=schedule,
                           seat_type=seat_type,
                           fare=fare,
                           avail=avail)


@booking_bp.route('/confirmation/<int:booking_id>')
@login_required
def confirmation(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    # make sure user can only see their own bookings
    if booking.passenger.user_id != current_user.user_id and not current_user.is_admin:
        flash('You do not have permission to view this booking.', 'danger')
        return redirect(url_for('main.index'))

    return render_template('booking/confirmation.html', booking=booking)


@booking_bp.route('/my-bookings')
@login_required
def my_bookings():
    passenger = current_user.passengers
    bookings = []
    waitlists = []

    if passenger:
        bookings = passenger.bookings.order_by(Booking.booking_time.desc()).all()
        waitlists = passenger.waitlist.order_by(Waitlist.request_time.desc()).all()

    return render_template('booking/my_bookings.html', bookings=bookings, waitlists=waitlists)


@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel(booking_id):
    booking = Booking.query.get_or_404(booking_id)

    if booking.passenger.user_id != current_user.user_id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('booking.my_bookings'))

    seat_type = booking.seat_type
    schedule_id = booking.schedule_id

    booking.status = BookingStatus.cancelled
    db.session.commit()

    # trigger the waitlist promotion logic
    _trigger_promote_waitlist(schedule_id, seat_type)

    flash('Your booking has been cancelled.', 'success')
    return redirect(url_for('booking.my_bookings'))
