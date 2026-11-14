from datetime import datetime
import enum

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager
from app.clock import local_now, utcnow


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# using enums for status fields so we dont have to hardcode strings everywhere
class UserRole(enum.Enum):
    passenger = 'passenger'
    admin = 'admin'

class BookingStatus(enum.Enum):
    confirmed = 'confirmed'
    cancelled = 'cancelled'
    waitlisted = 'waitlisted'

class SeatType(enum.Enum):
    economy = 'economy'
    premium_economy = 'premium_economy'
    business = 'business'


# seat class -> letter used in seat numbers (E12, P3, B7).
# This is also the list of seat classes the booking routes accept.
SEAT_PREFIX = {
    'economy': 'E',
    'premium_economy': 'P',
    'business': 'B',
}


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    address = db.Column(db.String(255))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.passenger, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    passengers = db.relationship('Passenger', back_populates='user', uselist=False)

    # flask-login needs this
    def get_id(self):
        return str(self.user_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == UserRole.admin


class Metro(db.Model):
    __tablename__ = 'metro'

    metro_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    metro_code = db.Column(db.String(20), unique=True, nullable=False)
    total_seats = db.Column(db.Integer, nullable=False, default=200)
    economy_seats = db.Column(db.Integer, default=100)
    premium_seats = db.Column(db.Integer, default=60)
    business_seats = db.Column(db.Integer, default=40)
    is_active = db.Column(db.Boolean, default=True)

    schedules = db.relationship('Schedule', back_populates='metro', lazy='dynamic')


class Station(db.Model):
    __tablename__ = 'station'

    station_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    location = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)


class Schedule(db.Model):
    __tablename__ = 'schedule'
    __table_args__ = (
        # the search page filters on exactly these three columns
        db.Index('ix_schedule_search', 'source_station_id', 'dest_station_id', 'travel_date'),
    )

    schedule_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    metro_id = db.Column(db.Integer, db.ForeignKey('metro.metro_id'), nullable=False)
    source_station_id = db.Column(db.Integer, db.ForeignKey('station.station_id'), nullable=False)
    dest_station_id = db.Column(db.Integer, db.ForeignKey('station.station_id'), nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    travel_date = db.Column(db.Date, nullable=False)
    economy_fare = db.Column(db.Numeric(8, 2), nullable=False, default=100)
    premium_fare = db.Column(db.Numeric(8, 2), nullable=False, default=160)
    business_fare = db.Column(db.Numeric(8, 2), nullable=False, default=240)
    is_active = db.Column(db.Boolean, default=True)

    metro = db.relationship('Metro', back_populates='schedules')
    source_station = db.relationship('Station', foreign_keys=[source_station_id])
    dest_station = db.relationship('Station', foreign_keys=[dest_station_id])
    bookings = db.relationship('Booking', back_populates='schedule', lazy='dynamic')
    routes = db.relationship('Route', back_populates='schedule', lazy='dynamic')
    waitlists = db.relationship('Waitlist', back_populates='schedule', lazy='dynamic')

    def booked_count(self, seat_type=None):
        q = self.bookings.filter_by(status=BookingStatus.confirmed)
        if seat_type:
            q = q.filter_by(seat_type=seat_type)
        return q.count()

    def capacity_for(self, seat_type):
        # map seat type string to actual capacity column
        capacity_map = {
            'economy': self.metro.economy_seats,
            'premium_economy': self.metro.premium_seats,
            'business': self.metro.business_seats,
        }
        return capacity_map.get(seat_type) or 0

    def available_seats(self, seat_type):
        """Seats left in a class. Used to show availability on the pages.

        The booking itself does not trust this number. It counts again while
        holding a lock on the schedule row (see app/services/booking.py).
        """
        return max(0, self.capacity_for(seat_type) - self.booked_count(seat_type))

    def fare_for(self, seat_type):
        fares = {
            'economy': float(self.economy_fare),
            'premium_economy': float(self.premium_fare),
            'business': float(self.business_fare),
        }
        return fares.get(seat_type, 0)

    def has_departed(self, now=None):
        now = now or local_now()
        return datetime.combine(self.travel_date, self.departure_time) <= now

    def is_bookable(self, now=None):
        return bool(self.is_active) and not self.has_departed(now)


# stop sequence for a schedule
class Route(db.Model):
    __tablename__ = 'route'

    route_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.schedule_id'), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('station.station_id'), nullable=False)
    stop_number = db.Column(db.Integer, nullable=False)

    schedule = db.relationship('Schedule', back_populates='routes')
    station = db.relationship('Station')


# linked 1-to-1 with user, holds travel-specific info
class Passenger(db.Model):
    __tablename__ = 'passenger'

    passenger_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False, unique=True)
    passenger_name = db.Column(db.String(150), nullable=False)
    age = db.Column(db.Integer)
    address = db.Column(db.String(255))
    phone_no = db.Column(db.String(15))
    pir_no = db.Column(db.String(30))

    user = db.relationship('User', back_populates='passengers')
    bookings = db.relationship('Booking', back_populates='passenger', lazy='dynamic')
    waitlist = db.relationship('Waitlist', back_populates='passenger', lazy='dynamic')


class Booking(db.Model):
    __tablename__ = 'booking'
    __table_args__ = (
        # One confirmed booking per seat on a train. active_seat is NULL for a
        # cancelled booking and a unique index ignores NULLs, so cancelling
        # frees the seat. This is the database's own guard against selling a
        # seat twice, on top of the row lock taken in the booking service.
        db.UniqueConstraint('schedule_id', 'active_seat', name='uq_booking_active_seat'),
        # the seat count query filters on these three columns
        db.Index('ix_booking_schedule_class_status', 'schedule_id', 'seat_type', 'status'),
    )

    booking_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.passenger_id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.schedule_id'), nullable=False)
    booking_time = db.Column(db.DateTime, default=utcnow)
    ticket_no = db.Column(db.String(30), unique=True, nullable=False)
    seat_type = db.Column(db.String(30), nullable=False)
    seat_number = db.Column(db.String(10))
    total_fare = db.Column(db.Numeric(8, 2), nullable=False)
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.confirmed, nullable=False)
    payment_method = db.Column(db.String(20))
    transaction_id = db.Column(db.String(50))
    # generated by the database: the seat number while the booking is confirmed, else NULL
    active_seat = db.Column(
        db.String(10),
        db.Computed("CASE WHEN status = 'confirmed' THEN seat_number ELSE NULL END", persisted=True),
    )

    passenger = db.relationship('Passenger', back_populates='bookings')
    schedule = db.relationship('Schedule', back_populates='bookings')


class Waitlist(db.Model):
    __tablename__ = 'waitlist'
    __table_args__ = (
        # a passenger can wait only once for the same train and class
        db.UniqueConstraint('passenger_id', 'schedule_id', 'seat_type', name='uq_waitlist_entry'),
        db.Index('ix_waitlist_queue', 'schedule_id', 'seat_type', 'position'),
    )

    waitlist_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.passenger_id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.schedule_id'), nullable=False)
    request_time = db.Column(db.DateTime, default=utcnow)
    seat_type = db.Column(db.String(30), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    passenger = db.relationship('Passenger', back_populates='waitlist')
    schedule = db.relationship('Schedule', back_populates='waitlists')
