from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Passenger, UserRole

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        age = request.form.get('age', '').strip()
        address = request.form.get('address', '').strip()

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            email=email,
            phone=phone,
            address=address,
            role=UserRole.passenger
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # need the user_id before creating passenger

        passenger = Passenger(
            user_id=user.user_id,
            passenger_name=username,
            age=int(age) if age.isdigit() else None,
            address=address,
            phone_no=phone
        )
        db.session.add(passenger)
        db.session.commit()

        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(next_page or url_for('main.index'))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    passenger = current_user.passengers

    if request.method == 'POST':
        current_user.username = request.form.get('username', current_user.username)
        current_user.phone = request.form.get('phone', current_user.phone)
        current_user.address = request.form.get('address', current_user.address)

        if passenger:
            passenger.passenger_name = current_user.username
            passenger.phone_no = current_user.phone
            passenger.address = current_user.address
            age_val = request.form.get('age', '')
            if age_val.isdigit():
                passenger.age = int(age_val)
            passenger.pir_no = request.form.get('pir_no', passenger.pir_no)

        db.session.commit()
        flash('Profile updated.', 'success')

    return render_template('auth/profile.html', passenger=passenger)
