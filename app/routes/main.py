from flask import Blueprint, render_template, request
from app.models import Schedule, Station, Metro
from datetime import date, datetime

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    stations = Station.query.filter_by(is_active=True).all()
    total_metros = Metro.query.count()
    total_stations = Station.query.count()
    # only count upcoming schedules
    total_schedules = Schedule.query.filter(Schedule.travel_date >= date.today()).count()
    return render_template('main/index.html',
                           stations=stations,
                           total_metros=total_metros,
                           total_stations=total_stations,
                           total_schedules=total_schedules)


@main_bp.route('/search')
def search():
    origin_id = request.args.get('origin', type=int)
    dest_id = request.args.get('destination', type=int)
    travel_date_str = request.args.get('date', '')

    stations = Station.query.filter_by(is_active=True).all()
    schedules = []

    if origin_id and dest_id and travel_date_str:
        try:
            travel_date = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
            schedules = Schedule.query.filter_by(
                source_station_id=origin_id,
                dest_station_id=dest_id,
                travel_date=travel_date,
                is_active=True
            ).all()
        except ValueError:
            pass  # bad date format, just show empty results

    return render_template('main/search.html',
                           stations=stations,
                           schedules=schedules,
                           selected_origin=origin_id,
                           selected_dest=dest_id,
                           selected_date=travel_date_str)


@main_bp.route('/about')
def about():
    return render_template('main/about.html')
