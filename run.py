from app import create_app, db
from app.models import User, Metro, Station, Schedule, Passenger, UserRole
from datetime import date, time

app = create_app()

# inject current time into all templates
@app.context_processor
def inject_globals():
    from datetime import datetime
    return {'now': datetime.now()}


def seed_demo_data():
    """
    Seeds some initial data so you can test things right away.
    Only runs if the db is empty.
    """
    if User.query.first():
        return

    print("Seeding demo data...")

    # create admin account
    admin = User(username='Admin', email='admin@subway.com', role=UserRole.admin)
    admin.set_password('admin123')
    db.session.add(admin)

    # create a demo passenger account
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

    # add metro lines
    blue_line = Metro(
        name='Blue Line',
        metro_code='BL01',
        economy_seats=100,
        premium_seats=60,
        business_seats=40
    )
    green_line = Metro(
        name='Green Line',
        metro_code='GL01',
        economy_seats=80,
        premium_seats=50,
        business_seats=30
    )
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

    # add a few schedules for today so you can test bookings immediately
    schedules = [
        Schedule(
            metro_id=blue_line.metro_id,
            source_station_id=stations[0].station_id,
            dest_station_id=stations[4].station_id,
            departure_time=time(7, 0),
            arrival_time=time(7, 45),
            travel_date=date.today(),
            economy_fare=100,
            premium_fare=160,
            business_fare=240
        ),
        Schedule(
            metro_id=blue_line.metro_id,
            source_station_id=stations[0].station_id,
            dest_station_id=stations[4].station_id,
            departure_time=time(9, 0),
            arrival_time=time(9, 45),
            travel_date=date.today(),
            economy_fare=100,
            premium_fare=160,
            business_fare=240
        ),
        Schedule(
            metro_id=green_line.metro_id,
            source_station_id=stations[1].station_id,
            dest_station_id=stations[3].station_id,
            departure_time=time(8, 30),
            arrival_time=time(9, 10),
            travel_date=date.today(),
            economy_fare=80,
            premium_fare=130,
            business_fare=200
        ),
        Schedule(
            metro_id=blue_line.metro_id,
            source_station_id=stations[6].station_id,
            dest_station_id=stations[2].station_id,
            departure_time=time(10, 0),
            arrival_time=time(10, 40),
            travel_date=date.today(),
            economy_fare=90,
            premium_fare=145,
            business_fare=220
        ),
    ]
    db.session.add_all(schedules)
    db.session.commit()
    print("Done. Demo data seeded.")


with app.app_context():
    db.create_all()
    seed_demo_data()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
