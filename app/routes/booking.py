from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from app.models import Booking, Waitlist, Schedule, SEAT_PREFIX
from app.services.booking import BookingError, book_seat, cancel_booking

booking_bp = Blueprint('booking', __name__)


def _passenger_or_redirect():
    """The logged-in user's passenger record, or a redirect to the profile page."""
    passenger = current_user.passengers
    if not passenger:
        flash('Please complete your profile before booking.', 'warning')
        return None, redirect(url_for('auth.profile'))
    return passenger, None


def _bookable_or_redirect(schedule):
    """Past and deactivated trains cannot be booked."""
    if not schedule.is_bookable():
        flash('This train is no longer available for booking.', 'warning')
        return redirect(url_for('main.search'))
    return None


@booking_bp.route('/select/<int:schedule_id>', methods=['GET'])
@login_required
def select(schedule_id):
    schedule = db.get_or_404(Schedule, schedule_id)
    passenger, stop = _passenger_or_redirect()
    if stop:
        return stop
    stop = _bookable_or_redirect(schedule)
    if stop:
        return stop

    seat_types = [
        {
            'key': 'economy',
            'label': 'Economy',
            'fare': float(schedule.economy_fare),
            'avail': schedule.available_seats('economy'),
            'capacity': schedule.capacity_for('economy'),
            'icon': '🪑'
        },
        {
            'key': 'premium_economy',
            'label': 'Premium Economy',
            'fare': float(schedule.premium_fare),
            'avail': schedule.available_seats('premium_economy'),
            'capacity': schedule.capacity_for('premium_economy'),
            'icon': '💺'
        },
        {
            'key': 'business',
            'label': 'Business',
            'fare': float(schedule.business_fare),
            'avail': schedule.available_seats('business'),
            'capacity': schedule.capacity_for('business'),
            'icon': '👑'
        },
    ]
    return render_template('booking/select.html', schedule=schedule, seat_types=seat_types)


@booking_bp.route('/payment/<int:schedule_id>/<seat_type>', methods=['GET', 'POST'])
@login_required
def payment(schedule_id, seat_type):
    if seat_type not in SEAT_PREFIX:
        abort(404)      # the seat class comes from the URL, so check it

    schedule = db.get_or_404(Schedule, schedule_id)
    passenger, stop = _passenger_or_redirect()
    if stop:
        return stop
    stop = _bookable_or_redirect(schedule)
    if stop:
        return stop

    if request.method == 'POST':
        pay_method = request.form.get('pay_method', 'upi')
        try:
            # checks the seat count under a row lock, see app/services/booking.py
            result = book_seat(passenger.passenger_id, schedule_id, seat_type, pay_method)
        except BookingError as err:
            flash(str(err), 'danger')
            return redirect(url_for('main.search'))

        if result.waitlisted:
            flash(f'This class is now full! You have been added to the waitlist at position #{result.waitlist_position}.', 'warning')
            return redirect(url_for('booking.my_bookings'))

        flash('Booking confirmed! Have a safe journey.', 'success')
        return redirect(url_for('booking.confirmation', booking_id=result.booking.booking_id))

    return render_template('booking/payment.html',
                           schedule=schedule,
                           seat_type=seat_type,
                           fare=schedule.fare_for(seat_type),
                           avail=schedule.available_seats(seat_type))


@booking_bp.route('/confirmation/<int:booking_id>')
@login_required
def confirmation(booking_id):
    booking = db.get_or_404(Booking, booking_id)

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
    booking = db.get_or_404(Booking, booking_id)

    if booking.passenger.user_id != current_user.user_id and not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('booking.my_bookings'))

    # cancel + waitlist promotion happen in one transaction
    result = cancel_booking(booking_id)
    if result.cancelled:
        flash('Your booking has been cancelled.', 'success')
    else:
        flash('This booking was already cancelled.', 'info')
    return redirect(url_for('booking.my_bookings'))
