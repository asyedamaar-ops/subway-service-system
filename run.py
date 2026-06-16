from app import create_app, db
from app.models import User, Metro, Station, Schedule, Passenger, UserRole
from datetime import date, time, timedelta

app = create_app()

@app.context_processor
def inject_globals():
    from datetime import datetime
    return {'now': datetime.now()}


def seed_demo_data():
    if User.query.first():
        # check if we need to add more schedules for future dates
        _ensure_future_schedules()
        return

    print("Seeding demo data...")

    # admin account
    admin = User(username='Admin', email='admin@subway.com', role=UserRole.admin)
    admin.set_password('admin123')
    db.session.add(admin)

    # demo passenger
    demo_user = User(
        username='Demo Passenger',
        email='demo@passenger.com',
        phone='+91 98765 43210',
        address='Chennai, Tamil Nadu',
        role=UserRole.passenger
    )
    demo_user.set_password('demo123')
    db.session.add(demo_user)
    db.session.flush()

    demo_passenger = Passenger(
        user_id=demo_user.user_id,
        passenger_name='Demo Passenger',
        age=21,
        address='Chennai, TN',
        phone_no='+91 98765 43210',
        pir_no='DEMO001'
    )
    db.session.add(demo_passenger)

    # metro lines
    blue_line = Metro(name='Blue Line', metro_code='BL01', economy_seats=100, premium_seats=60, business_seats=40)
    green_line = Metro(name='Green Line', metro_code='GL01', economy_seats=80, premium_seats=50, business_seats=30)
    db.session.add_all([blue_line, green_line])
    db.session.flush()

    # stations
    station_data = [
        ('Chennai Central', 'CNL', 'Park Town, Chennai'),
        ('Egmore', 'EGM', 'Egmore, Chennai'),
        ('Anna Nagar', 'ANN', 'Anna Nagar, Chennai'),
        ('Koyambedu', 'KYB', 'Koyambedu, Chennai'),
        ('Airport', 'CAP', 'Meenambakkam, Chennai'),
        ('Guindy', 'GDY', 'Guindy, Chennai'),
        ('T. Nagar', 'TNG', 'T. Nagar, Chennai'),
        ('Vadapalani', 'VDP', 'Vadapalani, Chennai'),
    ]
    stations = []
    for name, code, location in station_data:
        s = Station(name=name, code=code, location=location)
        db.session.add(s)
        stations.append(s)
    db.session.flush()

    # add schedules for next 60 days
    _add_schedules_for_range(blue_line, green_line, stations, date.today(), 60)

    db.session.commit()
    print("Done. Demo data seeded with 60 days of schedules.")


def _add_schedules_for_range(blue_line, green_line, stations, start_date, days):
    """Add schedules for every day in the given range"""
    # define daily schedule templates
    schedule_templates = [
        # (metro, from_idx, to_idx, depart, arrive, eco, prem, biz)
        (blue_line,  0, 4, time(6,  0), time(6, 45), 100, 160, 240),
        (blue_line,  0, 4, time(7,  0), time(7, 45), 100, 160, 240),
        (blue_line,  0, 4, time(8,  0), time(8, 45), 100, 160, 240),
        (blue_line,  0, 4, time(9,  0), time(9, 45), 100, 160, 240),
        (blue_line,  0, 4, time(10, 0), time(10,45), 100, 160, 240),
        (blue_line,  0, 4, time(12, 0), time(12,45), 100, 160, 240),
        (blue_line,  0, 4, time(14, 0), time(14,45), 100, 160, 240),
        (blue_line,  0, 4, time(16, 0), time(16,45), 100, 160, 240),
        (blue_line,  0, 4, time(18, 0), time(18,45), 100, 160, 240),
        (blue_line,  0, 4, time(20, 0), time(20,45), 100, 160, 240),
        # Airport -> Chennai Central (reverse)
        (blue_line,  4, 0, time(6, 30), time(7, 15), 100, 160, 240),
        (blue_line,  4, 0, time(8, 30), time(9, 15), 100, 160, 240),
        (blue_line,  4, 0, time(10,30), time(11,15), 100, 160, 240),
        (blue_line,  4, 0, time(13, 0), time(13,45), 100, 160, 240),
        (blue_line,  4, 0, time(17, 0), time(17,45), 100, 160, 240),
        (blue_line,  4, 0, time(19, 0), time(19,45), 100, 160, 240),
        # Green line routes
        (green_line, 1, 3, time(7,  0), time(7, 40),  80, 130, 200),
        (green_line, 1, 3, time(9,  0), time(9, 40),  80, 130, 200),
        (green_line, 1, 3, time(11, 0), time(11,40),  80, 130, 200),
        (green_line, 1, 3, time(14, 0), time(14,40),  80, 130, 200),
        (green_line, 1, 3, time(17, 0), time(17,40),  80, 130, 200),
        (green_line, 1, 3, time(19, 0), time(19,40),  80, 130, 200),
        # Koyambedu -> Egmore reverse
        (green_line, 3, 1, time(8,  0), time(8, 40),  80, 130, 200),
        (green_line, 3, 1, time(10, 0), time(10,40),  80, 130, 200),
        (green_line, 3, 1, time(15, 0), time(15,40),  80, 130, 200),
        (green_line, 3, 1, time(18, 0), time(18,40),  80, 130, 200),
        # T.Nagar <-> Anna Nagar
        (blue_line,  6, 2, time(7, 30), time(8, 10),  90, 145, 220),
        (blue_line,  6, 2, time(9, 30), time(10,10),  90, 145, 220),
        (blue_line,  6, 2, time(12,30), time(13,10),  90, 145, 220),
        (blue_line,  6, 2, time(17,30), time(18,10),  90, 145, 220),
        (blue_line,  2, 6, time(8, 30), time(9, 10),  90, 145, 220),
        (blue_line,  2, 6, time(11, 0), time(11,40),  90, 145, 220),
        (blue_line,  2, 6, time(16, 0), time(16,40),  90, 145, 220),
        # Chennai Central <-> T.Nagar
        (blue_line,  0, 6, time(7, 15), time(7, 50),  75, 120, 180),
        (blue_line,  0, 6, time(9, 15), time(9, 50),  75, 120, 180),
        (blue_line,  0, 6, time(13,15), time(13,50),  75, 120, 180),
        (blue_line,  0, 6, time(18,15), time(18,50),  75, 120, 180),
        # Guindy routes
        (blue_line,  0, 5, time(8, 0),  time(8, 35),  85, 135, 205),
        (blue_line,  0, 5, time(11, 0), time(11,35),  85, 135, 205),
        (blue_line,  0, 5, time(16, 0), time(16,35),  85, 135, 205),
        (blue_line,  5, 0, time(9, 0),  time(9, 35),  85, 135, 205),
        (blue_line,  5, 0, time(14, 0), time(14,35),  85, 135, 205),
        (blue_line,  5, 0, time(18, 0), time(18,35),  85, 135, 205),
    ]

    for i in range(days):
        travel_date = start_date + timedelta(days=i)
        for tmpl in schedule_templates:
            metro, from_idx, to_idx, dep, arr, eco, prem, biz = tmpl
            s = Schedule(
                metro_id=metro.metro_id,
                source_station_id=stations[from_idx].station_id,
                dest_station_id=stations[to_idx].station_id,
                departure_time=dep,
                arrival_time=arr,
                travel_date=travel_date,
                economy_fare=eco,
                premium_fare=prem,
                business_fare=biz
            )
            db.session.add(s)


def _ensure_future_schedules():
    """Called on subsequent startups to add schedules for dates not yet covered"""
    from app.models import Schedule
    from sqlalchemy import func

    max_date = db.session.query(func.max(Schedule.travel_date)).scalar()
    if not max_date:
        return

    today = date.today()
    target = today + timedelta(days=60)

    if max_date >= target:
        return  # already have enough future schedules

    # fetch metro and station objects
    blue_line  = Metro.query.filter_by(metro_code='BL01').first()
    green_line = Metro.query.filter_by(metro_code='GL01').first()
    if not blue_line or not green_line:
        return

    station_codes = ['CNL','EGM','ANN','KYB','CAP','GDY','TNG','VDP']
    stations = [Station.query.filter_by(code=c).first() for c in station_codes]
    if None in stations:
        return

    start = max_date + timedelta(days=1)
    days = (target - start).days + 1
    if days > 0:
        _add_schedules_for_range(blue_line, green_line, stations, start, days)
        db.session.commit()
        print(f"Added schedules from {start} to {target}")


with app.app_context():
    db.create_all()
    seed_demo_data()


if __name__ == '__main__':
    import os
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
