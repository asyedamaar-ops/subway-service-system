# Subway Service System

A metro ticketing web app i built for my DBMS course project at SRM. You can search for trains, book tickets, cancel them, and it handles waitlisting automatically when a train gets full.

The admin side lets you add metros/stations/schedules and see all bookings + revenue.

---

## What it does

- Search trains between stations on a given date
- Book tickets (economy / premium / business class)
- Mock payment (UPI, card, netbanking) — not real obviously
- If train is full, you get added to waitlist automatically
- When someone cancels, the first person on the waitlist gets the seat
- Admin panel to manage everything

## Tech used

- **Flask** (Python) for backend
- **MySQL** for database — all the schema design, normalization, triggers etc. is the main point of this project
- **SQLAlchemy** as ORM
- **Bootstrap 5** + custom CSS for frontend
- Flask-Login for auth

## Database stuff

This was the main focus of the project. The schema has 7 tables:

`user` → `passenger` (1-to-1), `metro`, `station`, `schedule`, `route`, `booking`, `waitlist`

All tables are normalized to 3NF/BCNF. The project report (included in repo) covers the full ER diagram, relational schema, normalization proof, and complex SQL queries.

There are 3 triggers:
1. Validates fare is not negative before insert
2. Auto-adds to waitlist when booking is attempted on a full train
3. Promotes waitlist when a booking is cancelled

There are also 3 views for common queries (booking details, revenue by metro, seat availability).

## How to run

You need Python 3.10+ and MySQL installed.

```bash
git clone https://github.com/asyedamaar-ops/subway-service-system
cd subway-service-system
pip install -r requirements.txt
```

Copy the env file and fill in your MySQL password:
```bash
cp .env.example .env
```

Create the database in MySQL:
```sql
CREATE DATABASE subway_system;
```

Then just run:
```bash
python run.py
```

It will create all the tables and seed some demo data automatically on first run.

Open `http://localhost:5000`

**Demo logins:**
- Admin: `admin@subway.com` / `admin123`
- Passenger: `demo@passenger.com` / `demo123`

## Project structure

```
subway/
├── run.py              # entry point, also handles db setup + seed
├── config.py
├── schema.sql          # raw SQL with triggers and views if you want to run it directly
├── requirements.txt
├── app/
│   ├── models.py       # all 7 SQLAlchemy models
│   ├── routes/
│   │   ├── auth.py     # login, register, profile
│   │   ├── main.py     # home, search
│   │   ├── booking.py  # booking flow + trigger logic
│   │   └── admin.py    # admin CRUD
│   ├── static/css/
│   │   └── style.css
│   └── templates/      # jinja2 templates
```

## Known issues / things i'd improve

- Payment is completely fake, just stores whatever method you pick
- Seat numbers are randomly assigned, not an actual seat map
- No email confirmation after booking
- The waitlist promotion trigger in schema.sql has a minor issue with the fare lookup — the app-level version in booking.py works correctly though
- Mobile layout could be better on very small screens


