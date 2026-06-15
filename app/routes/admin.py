from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Metro, Station, Schedule, Booking, Waitlist, Passenger, User, BookingStatus
from datetime import date, datetime
from functools import wraps
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin access for this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'total_bookings': Booking.query.count(),
        'confirmed': Booking.query.filter_by(status=BookingStatus.confirmed).count(),
        'cancelled': Booking.query.filter_by(status=BookingStatus.cancelled).count(),
        'waitlisted': Waitlist.query.count(),
        'total_passengers': Passenger.query.count(),
        'total_metros': Metro.query.count(),
        'total_stations': Station.query.count(),
        'total_schedules': Schedule.query.count(),
        'revenue': db.session.query(func.sum(Booking.total_fare)).filter_by(
            status=BookingStatus.confirmed).scalar() or 0,
    }
    recent_bookings = Booking.query.order_by(Booking.booking_time.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)


@admin_bp.route('/metros')
@login_required
@admin_required
def metros():
    metros = Metro.query.all()
    return render_template('admin/metros.html', metros=metros)


@admin_bp.route('/metros/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_metro():
    if request.method == 'POST':
        metro = Metro(
            name=request.form['name'],
            metro_code=request.form['metro_code'],
            total_seats=int(request.form.get('total_seats', 200)),
            economy_seats=int(request.form.get('economy_seats', 100)),
            premium_seats=int(request.form.get('premium_seats', 60)),
            business_seats=int(request.form.get('business_seats', 40)),
        )
        db.session.add(metro)
        db.session.commit()
        flash('Metro added successfully.', 'success')
        return redirect(url_for('admin.metros'))
    return render_template('admin/metro_form.html', metro=None)


@admin_bp.route('/metros/edit/<int:metro_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_metro(metro_id):
    metro = Metro.query.get_or_404(metro_id)
    if request.method == 'POST':
        metro.name = request.form['name']
        metro.metro_code = request.form['metro_code']
        metro.total_seats = int(request.form.get('total_seats', metro.total_seats))
        metro.economy_seats = int(request.form.get('economy_seats', metro.economy_seats))
        metro.premium_seats = int(request.form.get('premium_seats', metro.premium_seats))
        metro.business_seats = int(request.form.get('business_seats', metro.business_seats))
        metro.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        flash('Metro updated.', 'success')
        return redirect(url_for('admin.metros'))
    return render_template('admin/metro_form.html', metro=metro)


@admin_bp.route('/stations')
@login_required
@admin_required
def stations():
    stations = Station.query.all()
    return render_template('admin/stations.html', stations=stations)


@admin_bp.route('/stations/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_station():
    if request.method == 'POST':
        station = Station(
            name=request.form['name'],
            code=request.form['code'].upper(),
            location=request.form.get('location', '')
        )
        db.session.add(station)
        db.session.commit()
        flash('Station added.', 'success')
        return redirect(url_for('admin.stations'))
    return render_template('admin/station_form.html', station=None)


@admin_bp.route('/stations/edit/<int:station_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_station(station_id):
    station = Station.query.get_or_404(station_id)
    if request.method == 'POST':
        station.name = request.form['name']
        station.code = request.form['code'].upper()
        station.location = request.form.get('location', station.location)
        station.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        flash('Station updated.', 'success')
        return redirect(url_for('admin.stations'))
    return render_template('admin/station_form.html', station=station)


@admin_bp.route('/schedules')
@login_required
@admin_required
def schedules():
    schedules = Schedule.query.order_by(Schedule.travel_date.desc()).all()
    return render_template('admin/schedules.html', schedules=schedules)


@admin_bp.route('/schedules/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_schedule():
    metros = Metro.query.filter_by(is_active=True).all()
    stations = Station.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        try:
            schedule = Schedule(
                metro_id=int(request.form['metro_id']),
                source_station_id=int(request.form['source_station_id']),
                dest_station_id=int(request.form['dest_station_id']),
                departure_time=datetime.strptime(request.form['departure_time'], '%H:%M').time(),
                arrival_time=datetime.strptime(request.form['arrival_time'], '%H:%M').time(),
                travel_date=datetime.strptime(request.form['travel_date'], '%Y-%m-%d').date(),
                economy_fare=float(request.form.get('economy_fare', 100)),
                premium_fare=float(request.form.get('premium_fare', 160)),
                business_fare=float(request.form.get('business_fare', 240)),
            )
            db.session.add(schedule)
            db.session.commit()
            flash('Schedule added.', 'success')
            return redirect(url_for('admin.schedules'))
        except Exception as e:
            flash(f'Something went wrong: {e}', 'danger')
    return render_template('admin/schedule_form.html', metros=metros, stations=stations, schedule=None)


@admin_bp.route('/bookings')
@login_required
@admin_required
def bookings():
    bookings = Booking.query.order_by(Booking.booking_time.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)


@admin_bp.route('/passengers')
@login_required
@admin_required
def passengers():
    passengers = Passenger.query.all()
    return render_template('admin/passengers.html', passengers=passengers)


@admin_bp.route('/waitlist')
@login_required
@admin_required
def waitlist():
    waitlist = Waitlist.query.order_by(Waitlist.schedule_id, Waitlist.position).all()
    return render_template('admin/waitlist.html', waitlist=waitlist)
