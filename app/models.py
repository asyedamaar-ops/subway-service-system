from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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


class User(db.Model, UserMixin):
    __tablename__ = 'user'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    address = db.Column(db.String(255))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.passenger, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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

    def available_seats(self, seat_type):
        # map seat type string to actual capacity column
        capacity_map = {
            'economy': self.metro.economy_seats,
            'premium_economy': self.metro.premium_seats,
            'business': self.metro.business_seats,
        }
        cap = capacity_map.get(seat_type, 0)
        used = self.booked_count(seat_type)
        return max(0, cap - used)

    def fare_for(self, seat_type):
        fares = {
            'economy': float(self.economy_fare),
            'premium_economy': float(self.premium_fare),
            'business': float(self.business_fare),
        }
        return fares.get(seat_type, 0)


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

    booking_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.passenger_id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.schedule_id'), nullable=False)
    booking_time = db.Column(db.DateTime, default=datetime.utcnow)
    ticket_no = db.Column(db.String(30), unique=True, nullable=False)
    seat_type = db.Column(db.String(30), nullable=False)
    seat_number = db.Column(db.String(10))
    total_fare = db.Column(db.Numeric(8, 2), nullable=False)
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.confirmed, nullable=False)
    payment_method = db.Column(db.String(20))
    transaction_id = db.Column(db.String(50))

    passenger = db.relationship('Passenger', back_populates='bookings')
    schedule = db.relationship('Schedule', back_populates='bookings')


class Waitlist(db.Model):
    __tablename__ = 'waitlist'

    waitlist_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    passenger_id = db.Column(db.Integer, db.ForeignKey('passenger.passenger_id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.schedule_id'), nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.utcnow)
    seat_type = db.Column(db.String(30), nullable=False)
    position = db.Column(db.Integer, nullable=False)

    passenger = db.relationship('Passenger', back_populates='waitlist')
    schedule = db.relationship('Schedule', back_populates='waitlists')
