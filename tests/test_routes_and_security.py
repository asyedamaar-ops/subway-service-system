"""Pages, access control, CSRF and redirect checks."""
import pytest

from app import db
from app.models import Booking, BookingStatus, UserRole, Waitlist
from app.security import is_safe_redirect_target
from app.services.booking import book_seat
from tests.conftest import PASSWORD, add_schedule, add_user, login, make_app


def test_public_pages_load(client, schedule):
    assert client.get('/').status_code == 200
    assert client.get('/about').status_code == 200
    assert client.get('/auth/login').status_code == 200
    assert client.get('/auth/register').status_code == 200
    page = client.get(f'/search?origin={schedule.source_station_id}'
                      f'&destination={schedule.dest_station_id}&date={schedule.travel_date}')
    assert page.status_code == 200 and b'08:00' in page.data


def test_search_hides_departed_trains(client, app):
    old = add_schedule(days_ahead=-1)
    page = client.get(f'/search?origin={old.source_station_id}'
                      f'&destination={old.dest_station_id}&date={old.travel_date}')
    assert b'08:00' not in page.data


def test_register_then_login(client, app):
    form = {'username': 'Asha', 'email': 'Asha@Example.com', 'password': 'longenough1',
            'confirm_password': 'longenough1', 'phone': '', 'age': '21', 'address': ''}
    assert client.post('/auth/register', data=form).status_code == 302
    assert client.post('/auth/login', data={'email': 'asha@example.com', 'password': 'longenough1'}).status_code == 302
    assert client.get('/booking/my-bookings').status_code == 200


@pytest.mark.parametrize('change', [
    {'password': 'short', 'confirm_password': 'short'},
    {'email': 'not-an-email'},
    {'confirm_password': 'different123'},
    {'username': '   '},
])
def test_register_rejects_bad_input(client, app, change):
    form = {'username': 'Asha', 'email': 'asha@example.com', 'password': 'longenough1',
            'confirm_password': 'longenough1'}
    form.update(change)
    assert client.post('/auth/register', data=form).status_code == 200      # form shown again
    assert client.post('/auth/login', data={'email': 'asha@example.com', 'password': form['password']}).status_code == 200


def test_booking_pages_require_login(client, schedule):
    for url in (f'/booking/select/{schedule.schedule_id}', '/booking/my-bookings'):
        response = client.get(url)
        assert response.status_code == 302 and '/auth/login' in response.headers['Location']


def test_full_booking_flow_through_the_pages(client, passengers, schedule):
    sid = schedule.schedule_id
    login(client, 'p1')
    assert client.get(f'/booking/select/{sid}').status_code == 200
    assert client.get(f'/booking/payment/{sid}/business').status_code == 200

    done = client.post(f'/booking/payment/{sid}/business', data={'pay_method': 'card'})
    assert done.status_code == 302 and '/booking/confirmation/' in done.headers['Location']
    assert client.get(done.headers['Location']).status_code == 200

    booking = Booking.query.one()
    assert client.post(f'/booking/cancel/{booking.booking_id}').status_code == 302
    assert db.session.get(Booking, booking.booking_id).status == BookingStatus.cancelled


def test_full_class_redirects_to_waitlist(client, passengers, schedule):
    sid = schedule.schedule_id
    book_seat(passengers[0], sid, 'business')
    login(client, 'p2')
    response = client.post(f'/booking/payment/{sid}/business', data={'pay_method': 'upi'})
    assert response.status_code == 302 and '/booking/my-bookings' in response.headers['Location']
    assert Waitlist.query.count() == 1


def test_seat_class_in_the_url_is_checked(client, passengers, schedule):
    login(client, 'p1')
    assert client.get(f'/booking/payment/{schedule.schedule_id}/first_class').status_code == 404
    assert client.post(f'/booking/payment/{schedule.schedule_id}/first_class',
                       data={'pay_method': 'upi'}).status_code == 404
    assert Booking.query.count() == 0 and Waitlist.query.count() == 0


def test_departed_train_cannot_be_opened_for_booking(client, passengers):
    old = add_schedule(days_ahead=-1)
    login(client, 'p1')
    response = client.post(f'/booking/payment/{old.schedule_id}/economy', data={'pay_method': 'upi'})
    assert response.status_code == 302 and Booking.query.count() == 0


def test_user_without_passenger_profile_is_sent_to_profile(client, app, schedule):
    add_user('boss', role=UserRole.admin, with_passenger=False)
    login(client, 'boss')
    response = client.post(f'/booking/payment/{schedule.schedule_id}/economy', data={'pay_method': 'upi'})
    assert response.status_code == 302 and '/auth/profile' in response.headers['Location']
    # saving the profile creates the passenger record
    client.post('/auth/profile', data={'username': 'boss', 'phone': '', 'address': '', 'age': '30'})
    assert client.get(f'/booking/select/{schedule.schedule_id}').status_code == 200


def test_cannot_cancel_or_view_someone_elses_booking(client, passengers, schedule):
    booking = book_seat(passengers[0], schedule.schedule_id, 'economy').booking
    login(client, 'p2')

    client.post(f'/booking/cancel/{booking.booking_id}')
    assert db.session.get(Booking, booking.booking_id).status == BookingStatus.confirmed
    assert client.get(f'/booking/confirmation/{booking.booking_id}').status_code == 302


def test_admin_pages_need_the_admin_role(client, passengers, schedule):
    add_user('boss', role=UserRole.admin, with_passenger=False)
    admin_pages = ['/admin/', '/admin/metros', '/admin/stations', '/admin/schedules',
                   '/admin/bookings', '/admin/passengers', '/admin/waitlist']

    login(client, 'p1')
    for url in admin_pages:
        assert client.get(url).status_code == 302          # passenger is turned away
    client.post('/auth/logout')

    login(client, 'boss')
    for url in admin_pages:
        assert client.get(url).status_code == 200


def test_logout_only_works_as_post(client, passengers):
    login(client, 'p1')
    assert client.get('/auth/logout').status_code == 405
    assert client.get('/booking/my-bookings').status_code == 200          # still logged in
    assert client.post('/auth/logout').status_code == 302
    assert client.get('/booking/my-bookings').status_code == 302          # logged out


# ---- CSRF -------------------------------------------------------------------

@pytest.fixture
def csrf_client():
    app = make_app(WTF_CSRF_ENABLED=True)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def _token(client, url='/auth/login'):
    html = client.get(url).get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start:html.index('"', start)]


def test_post_without_csrf_token_is_rejected(csrf_client):
    passenger_id = add_user('p1').passengers.passenger_id
    schedule = add_schedule()
    booking = book_seat(passenger_id, schedule.schedule_id, 'economy').booking

    # login itself needs the token
    assert csrf_client.post('/auth/login', data={'email': 'p1@example.com', 'password': PASSWORD}).status_code == 400
    token = _token(csrf_client)
    assert csrf_client.post('/auth/login', data={'email': 'p1@example.com', 'password': PASSWORD,
                                                 'csrf_token': token}).status_code == 302

    # a forged cancel request (no token) changes nothing
    assert csrf_client.post(f'/booking/cancel/{booking.booking_id}').status_code == 400
    assert db.session.get(Booking, booking.booking_id).status == BookingStatus.confirmed

    # the real form carries the token and works
    token = _token(csrf_client, '/booking/my-bookings')
    assert csrf_client.post(f'/booking/cancel/{booking.booking_id}', data={'csrf_token': token}).status_code == 302
    assert db.session.get(Booking, booking.booking_id).status == BookingStatus.cancelled


def test_every_post_form_carries_a_csrf_token(csrf_client):
    add_user('boss', role=UserRole.admin)
    schedule = add_schedule()
    token = _token(csrf_client)
    csrf_client.post('/auth/login', data={'email': 'boss@example.com', 'password': PASSWORD, 'csrf_token': token})
    pages = ['/auth/profile', '/admin/metros/add', '/admin/stations/add', '/admin/schedules/add',
             f'/booking/payment/{schedule.schedule_id}/economy', '/admin/']
    for url in pages:
        html = csrf_client.get(url).get_data(as_text=True)
        assert html.count('<form method="POST"') == html.count('name="csrf_token"'), url


# ---- open redirect ----------------------------------------------------------

@pytest.mark.parametrize('target, safe', [
    ('/booking/my-bookings', True),
    ('/search?origin=1&destination=2', True),
    ('https://evil.example/', False),
    ('//evil.example/', False),
    ('/\\evil.example', False),
    ('javascript:alert(1)', False),
    ('booking/my-bookings', False),
    ('', False),
    (None, False),
])
def test_is_safe_redirect_target(app, target, safe):
    with app.test_request_context('/auth/login'):
        assert is_safe_redirect_target(target) is safe


def test_login_does_not_follow_an_external_next(client, passengers):
    data = {'email': 'p1@example.com', 'password': PASSWORD}
    away = client.post('/auth/login?next=https://evil.example/', data=data)
    assert away.status_code == 302 and 'evil.example' not in away.headers['Location']
    client.post('/auth/logout')
    back = client.post('/auth/login?next=/booking/my-bookings', data=data)
    assert back.headers['Location'].endswith('/booking/my-bookings')
