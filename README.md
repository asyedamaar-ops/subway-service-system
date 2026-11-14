# Subway Service System

**Metro ticket booking that cannot sell the same seat twice.** A Flask and MySQL web app with three seat classes, an automatic first-in-first-out waitlist, and an admin panel.

![tests](https://github.com/asyedamaar-ops/subway-service-system/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?style=flat-square&logo=mysql&logoColor=white)

Built for the DBMS course at SRM Institute of Science and Technology. Passengers search trains, book Economy, Premium Economy or Business seats, cancel bookings, and join a waitlist when a class is full. Admins manage metros, stations, schedules, bookings and the waitlist.

> **Status:** the hosted demo has been taken down. The screenshots below come from a local run. Instructions to run it yourself are further down.

## Team and my role

Team of 2.

| Part | Who |
|---|---|
| Database design (schema, views, triggers) and the Flask backend: authentication, role-based access, booking, cancellation, waitlist, admin module | Syed Amaar Andrabi (me) |
| Frontend pages (HTML, CSS, Bootstrap) and the original deployment | Devdarsh Singh |

## Screenshots

| Search results | Choose a class |
|---|---|
| ![Search](docs/screenshots/02_search_results.png) | ![Select](docs/screenshots/03_select_class.png) |

| Class full, so the passenger joins the waitlist | Admin waitlist view |
|---|---|
| ![Waitlist](docs/screenshots/05_added_to_waitlist.png) | ![Admin](docs/screenshots/06_admin_waitlist.png) |

After a confirmed booking on the same train is cancelled, the first waitlisted passenger is promoted automatically:

![Promoted](docs/screenshots/07_waitlist_promoted_after_cancel.png)

## How a booking works

```mermaid
flowchart TD
    A[Passenger pays for a seat] --> B[Start transaction and lock the schedule row<br/>SELECT ... FOR UPDATE]
    B --> C[Count confirmed bookings of that class<br/>with a locking read]
    C --> D{Seat free?}
    D -- yes --> E[Insert booking with the lowest free seat number]
    D -- no --> F[Add passenger to the end of the waitlist]
    E --> G[Commit, lock released]
    F --> G
    H[Passenger cancels] --> I[Lock the schedule row, then the booking row]
    I --> J{Still confirmed?}
    J -- no --> K[Do nothing]
    J -- yes --> L[Mark cancelled, give the seat to waitlist position 1,<br/>move everyone else up one place]
    L --> G
```

All of this lives in one file, [`app/services/booking.py`](app/services/booking.py). The routes only call it.

## How overselling is prevented

The first version checked the seat count and then inserted the booking as two separate steps. Two requests could both see "1 seat left" and both book it. I reproduced this on MariaDB with one seat and 8 simultaneous requests: between 2 and 6 bookings were confirmed, depending on the run. Sending the same cancel request twice also promoted two waitlisted passengers into one seat.

The fix has three layers:

1. **Row lock.** Booking and cancelling both start with `SELECT ... FOR UPDATE` on the schedule row, so requests for the same train run one after another.
2. **Locking reads.** The seat count and the waitlist are also read with `FOR UPDATE`. Under MySQL's default isolation level (REPEATABLE READ) a plain `SELECT` can return an older snapshot, so the lock alone is not enough. I checked this by switching the seat count back to a plain read: the last-seat test then fails.
3. **Unique index in the database.** `booking.active_seat` is a generated column that holds the seat number while a booking is confirmed and `NULL` after it is cancelled. A unique index on `(schedule_id, active_seat)` makes the database itself refuse a second confirmed booking on the same seat.

Cancelling and promoting the next passenger is one transaction. A booking that is already cancelled is left alone, so a repeated request changes nothing.

After the fix, 12 simultaneous requests for one seat give exactly 1 confirmed booking and waitlist positions 1 to 11.

## Features

- Search trains between two stations on a given date. Trains that have already left are hidden
- Book Economy, Premium Economy or Business seats (fare multipliers 1.0x, 1.6x and 2.4x of the base fare)
- Per-class seat availability for every schedule, with seat numbers given in order (E1, E2, ...)
- Automatic waitlisting when a class is full, with first-in-first-out promotion when a booking is cancelled
- Mock payment (UPI, card, net banking), with no real payment processing
- Admin panel with CRUD for metros, stations and schedules, plus bookings, passengers and waitlist views

## Database

```mermaid
erDiagram
    USER ||--o| PASSENGER : "has profile"
    PASSENGER ||--o{ BOOKING : makes
    PASSENGER ||--o{ WAITLIST : "waits in"
    METRO ||--o{ SCHEDULE : runs
    STATION ||--o{ SCHEDULE : "source / destination"
    SCHEDULE ||--o{ BOOKING : "is booked by"
    SCHEDULE ||--o{ WAITLIST : "has queue"
    SCHEDULE ||--o{ ROUTE : "stops at"
    STATION ||--o{ ROUTE : "is a stop on"
```

- 8 tables: `user`, `passenger`, `metro`, `station`, `route`, `schedule`, `booking`, `waitlist`
- 3 views in `schema.sql`: booking details, revenue by metro and seat availability
- 2 triggers in `schema.sql`: a negative fare is rejected, and a cancelled booking cannot be switched back to confirmed
- Constraints and indexes: unique seat per train (`uq_booking_active_seat`), one waitlist entry per passenger, train and class (`uq_waitlist_entry`), and indexes for the search page, the seat count and the waitlist queue
- The app creates the same tables through SQLAlchemy (`app/models.py`), so loading `schema.sql` is optional. The triggers only reject bad data, so they are safe to use together with the app
- Waitlist promotion is not a trigger. An earlier `AFTER UPDATE` trigger on `booking` tried to insert the promoted booking into `booking`. MySQL does not let a trigger change the table that fired it (error 1442), so every cancellation failed as soon as somebody was waiting. Promotion now runs in the application transaction only
- Seed data: 2 lines (Blue and Green), 8 stations, 9 directional routes and 2,580 daily schedules over 60 days. The seed tops itself up on each start

## Security

- Passwords are stored as salted hashes (Werkzeug)
- Every POST form carries a CSRF token (Flask-WTF `CSRFProtect`). A forged request without it gets a 400
- Logout is a POST, so a link on another site cannot log a user out
- After login, `?next=` is followed only when it points back into this site (no open redirect)
- Passengers can only see and cancel their own bookings. Admin pages need the admin role
- Session cookies are HttpOnly and SameSite=Lax, and HTTPS-only when `APP_ENV=production`
- In production the app refuses to start without a real `SECRET_KEY`, and the admin account is created only when `ADMIN_PASSWORD` is set

## Tests

44 tests with pytest.

```bash
pip install -r requirements-dev.txt
pytest
```

- 40 tests run on an in-memory SQLite database and need no setup. They cover the booking rules, the waitlist order, the double-cancel bug, page access, CSRF and redirects.
- 4 tests need real row locks, so they run only against MySQL or MariaDB. They fire 12 threads at the same seat and also mix cancellations with new bookings.

```bash
TEST_DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/subway_test pytest
```

The GitHub Actions workflow runs all 44 on every push, with a MySQL 8 service for the lock tests.

## Tech stack

Flask, SQLAlchemy, Flask-Login, Flask-WTF, PyMySQL, MySQL, Bootstrap 5, gunicorn, pytest.

## Run it locally

You need Python 3.11+ and MySQL 8 (or MariaDB 10.5+).

```bash
git clone https://github.com/asyedamaar-ops/subway-service-system
cd subway-service-system
pip install -r requirements.txt
cp .env.example .env     # set DB_USER and DB_PASSWORD for your MySQL
# create an empty database first: CREATE DATABASE subway_system;
python run.py
```

On first start `run.py` creates the tables and seeds demo data. Open http://localhost:5000. The seed creates a demo passenger (`demo@passenger.com`) and an admin account (`admin@subway.com`). Their local passwords are in `app/seed.py`.

If you created the database with a version from before November 2026, drop it and let the app create it again. The `booking` and `waitlist` tables gained columns and indexes.

## Deploy

The `Procfile` starts the app with gunicorn (`gunicorn run:app`). On the host, set:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | a long random string |
| `DATABASE_URL` | `mysql://user:password@host:3306/dbname` (or the five `DB_*` values) |
| `SEED_DEMO_DATA` | `1` if you want the demo lines and schedules |
| `ADMIN_PASSWORD` | your own admin password |

## Known limitations

- Payment is a mock and only stores the chosen method
- No seat map. The lowest free seat number in the class is assigned
- No email confirmation and no rate limiting on login
- A waitlisted passenger is promoted without a payment step
- No schema migrations. A schema change means recreating the database
- The app is not deployed at the moment

## Change log

**November 2026: correctness and security pass** (done with an AI coding assistant, see the commit history)

- Fixed overselling under concurrent bookings (row lock, locking reads, unique seat index)
- Fixed the repeated-cancel bug that promoted two passengers into one seat
- Removed the SQL promotion trigger that could never work on MySQL (error 1442)
- Turned on CSRF protection, made logout a POST, closed the open redirect on login
- Checked the seat class from the URL, blocked bookings on departed trains, fixed a crash for accounts without a passenger profile
- Seat numbers are now assigned in order and are unique per train
- Moved the booking rules into `app/services/booking.py` and added 44 tests and a CI workflow
- Updated all dependencies and switched the production server to gunicorn
