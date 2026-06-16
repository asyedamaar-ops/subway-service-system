# Subway Service System

A metro ticketing web app built for my DBMS course project at SRM. You can search for trains, book tickets, cancel them, and it handles waitlisting automatically when a train gets full.

## 🚇 Live Demo

**[https://subway-service-system-production.up.railway.app](https://subway-service-system-production.up.railway.app)**

| Role | Email | Password |
|---|---|---|
| Passenger | demo@passenger.com | demo123 |
| Admin | admin@subway.com | admin123 |

## Available Routes

| From | To | Line | Fare (Economy) |
|---|---|---|---|
| Chennai Central (CNL) | Airport (CAP) | Blue Line | ₹100 |
| Airport (CAP) | Chennai Central (CNL) | Blue Line | ₹100 |
| Egmore (EGM) | Koyambedu (KYB) | Green Line | ₹80 |
| Koyambedu (KYB) | Egmore (EGM) | Green Line | ₹80 |
| T. Nagar (TNG) | Anna Nagar (ANN) | Blue Line | ₹90 |
| Anna Nagar (ANN) | T. Nagar (TNG) | Blue Line | ₹90 |
| Chennai Central (CNL) | T. Nagar (TNG) | Blue Line | ₹75 |
| T. Nagar (TNG) | Chennai Central (CNL) | Blue Line | ₹75 |
| Chennai Central (CNL) | Guindy (GDY) | Blue Line | ₹85 |
| Guindy (GDY) | Chennai Central (CNL) | Blue Line | ₹85 |

Schedules run daily from **6:00 AM to 8:00 PM** with trains every 1-2 hours. All routes are available for the next 60 days from deployment.

## Seat Classes

| Class | Multiplier | Example (CNL→CAP) |
|---|---|---|
| Economy | Base fare | ₹100 |
| Premium Economy | 1.6x | ₹160 |
| Business | 2.4x | ₹240 |

## What it does

- Search trains between stations on a given date
- Book tickets (economy / premium / business class)
- Mock payment (UPI, card, netbanking)
- If train is full, you get added to waitlist automatically
- When someone cancels, the first person on the waitlist gets the seat
- Admin panel to manage everything

## Tech used

- **Flask** (Python) for backend
- **MySQL** for database — schema design, normalization, triggers etc. is the main point of this project
- **SQLAlchemy** as ORM
- **Bootstrap 5** + custom CSS for frontend
- Flask-Login for auth
- Deployed on **Railway**

## Database stuff

This was the main focus of the project. The schema has 7 tables:

`user` → `passenger` (1-to-1), `metro`, `station`, `schedule`, `route`, `booking`, `waitlist`

All tables are normalized to 3NF/BCNF. The project report covers the full ER diagram, relational schema, normalization proof, and complex SQL queries.

There are 3 triggers:
1. Validates fare is not negative before insert
2. Auto-adds to waitlist when booking is attempted on a full train
3. Promotes waitlist when a booking is cancelled

There are also 3 views for common queries (booking details, revenue by metro, seat availability).

## How to run locally

You need Python 3.10+ and MySQL installed.

```bash
git clone https://github.com/asyedamaar-ops/subway-service-system
cd subway-service-system
pip install -r requirements.txt
cp .env.example .env
# edit .env with your MySQL password
python run.py
```

Open `http://localhost:5000`

## Known issues / things i'd improve

- Payment is completely fake, just stores whatever method you pick
- Seat numbers are randomly assigned, not an actual seat map
- No email confirmation after booking
- Mobile layout could be better on very small screens
- Would add more routes and stations in a real version

## Academic context

Course: 21CSC205P Database Management Systems
Guide: Dr. A. Sheryl Oliver, Dept. of CINTEL, SRMIST-KTR
Team: Syed Amaar Andrabi (RA2311026010439), Devdarsh Singh (RA2311026010443)
Year: 2024-25
