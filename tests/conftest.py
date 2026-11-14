"""Shared test setup.

The tests run on an in-memory SQLite database, so they need no MySQL server.
The one test that needs real row locks (test_concurrency_mysql.py) runs only
when TEST_DATABASE_URL points at a MySQL or MariaDB database.
"""
from datetime import time, timedelta

import pytest

from app import create_app, db
from app.clock import local_today
from app.models import Metro, Passenger, Schedule, Station, User, UserRole

PASSWORD = 'password123'


def make_app(**overrides):
    config = {
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'SQLALCHEMY_ENGINE_OPTIONS': {},
        'WTF_CSRF_ENABLED': False,      # switched on in the CSRF tests
    }
    config.update(overrides)
    return create_app(config)


def add_user(name, role=UserRole.passenger, with_passenger=True):
    user = User(username=name, email=f'{name}@example.com', role=role)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.flush()
    if with_passenger:
        db.session.add(Passenger(user_id=user.user_id, passenger_name=name))
    db.session.commit()
    return user


def add_schedule(economy=2, premium=1, business=1, days_ahead=3):
    """One train with small classes, so a class fills up after a few bookings."""
    count = Metro.query.count()
    metro = Metro(name=f'Line {count}', metro_code=f'L{count}', total_seats=economy + premium + business,
                  economy_seats=economy, premium_seats=premium, business_seats=business)
    src = Station(name=f'From {count}', code=f'F{count}')
    dst = Station(name=f'To {count}', code=f'T{count}')
    db.session.add_all([metro, src, dst])
    db.session.flush()
    schedule = Schedule(
        metro_id=metro.metro_id, source_station_id=src.station_id, dest_station_id=dst.station_id,
        departure_time=time(8, 0), arrival_time=time(8, 45),
        travel_date=local_today() + timedelta(days=days_ahead),
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def login(client, name):
    return client.post('/auth/login', data={'email': f'{name}@example.com', 'password': PASSWORD})


@pytest.fixture
def app():
    app = make_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def passengers(app):
    """Four passenger accounts: p1 .. p4. Returns their passenger ids."""
    return [add_user(f'p{i}').passengers.passenger_id for i in range(1, 5)]


@pytest.fixture
def schedule(app):
    """A train with 2 economy seats, 1 premium seat and 1 business seat."""
    return add_schedule()
