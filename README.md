# Subway Service System

A metro ticketing web app built for the DBMS course at SRM. It lets passengers search trains, book tickets in three seat classes, cancel bookings, and join an automatic waitlist when a class is full. An admin panel manages metros, stations, schedules, bookings and the waitlist.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=flat-square&logo=mysql&logoColor=white)

> **Status:** the hosted demo has been taken down. The screenshots below come from a local run. Instructions to run it yourself are further down.

## My role

Backend and database developer in a team of 3, with separate frontend and UI/UX developers. I designed the MySQL schema and wrote the Flask backend: authentication, role-based access, booking and cancellation, the waitlist logic and the admin module.

## Screenshots

| Search results | Choose a class |
|---|---|
| ![Search](screenshots/02_search_results.png) | ![Select](screenshots/03_select_class.png) |

| Class full, so the passenger joins the waitlist | Admin waitlist view |
|---|---|
| ![Waitlist](screenshots/05_added_to_waitlist.png) | ![Admin](screenshots/06_admin_waitlist.png) |

After a confirmed booking on the same train is cancelled, the first waitlisted passenger is promoted automatically:

![Promoted](screenshots/07_waitlist_promoted_after_cancel.png)

## Features

- Search trains between two stations on a given date
- Book Economy, Premium Economy or Business seats (fare multipliers 1.0x, 1.6x and 2.4x of the base fare)
- Per-class seat availability for every schedule
- Automatic waitlisting when a class is full, with first-in-first-out promotion when a booking is cancelled
- Mock payment (UPI, card, net banking), with no real payment processing
- Admin panel with CRUD for metros, stations and schedules, plus bookings, passengers and waitlist views

## Database

- 8 tables: `user`, `passenger`, `metro`, `station`, `route`, `schedule`, `booking`, `waitlist`
- 3 views in `schema.sql`: booking details, revenue by metro and seat availability
- 2 SQL triggers in `schema.sql`: a fare check before a booking insert, and waitlist promotion after a cancellation
- Waitlist **joining** is handled in the Flask code. The deployed app created its tables through SQLAlchemy, so waitlist promotion ran in the application code (`_trigger_promote_waitlist`) and not through the SQL trigger. Use one path or the other, not both, or a cancellation could promote two passengers.
- Seed data: 2 lines (Blue and Green), 8 stations, 9 directional routes and 2,580 daily schedules over 60 days. The seed tops itself up on each start.

## Tech stack

Flask, SQLAlchemy, Flask-Login, PyMySQL, MySQL, Bootstrap 5.

## Run it locally

You need Python 3.10+ and MySQL.

```bash
git clone https://github.com/asyedamaar-ops/subway-service-system
cd subway-service-system
pip install -r requirements.txt
cp .env.example .env     # set DB_USER and DB_PASSWORD for your MySQL
# create an empty database first: CREATE DATABASE subway_system;
python run.py
```

On first start `run.py` creates the tables and seeds demo data. Open http://localhost:5000. The seed creates a demo passenger and an admin account. Their login details are in `run.py`. Change them before deploying anywhere public.

## Known limitations

- Payment is a mock and only stores the chosen method
- Seat numbers are assigned randomly, with no seat map
- No email confirmation
- It runs on the Flask development server (`python run.py`). A production setup would use gunicorn behind a proper host
- The secret key falls back to a development value if `SECRET_KEY` is not set
- Passwords for the seeded demo accounts are fixed in the seed script
