from flask import render_template, request, redirect, url_for
from app.auth import auth_bp
from app.auth.services import authenticate, register_user, reset_user_password
from flask_login import login_user, logout_user, login_required, current_user
from app.models.enums import RoleType
from app.models import AboutPage


@auth_bp.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.role_type == RoleType.SPONSOR:
        return redirect(url_for('sponsor.dashboard'))

    if current_user.role_type == RoleType.ADMIN:
        return redirect(url_for('admin.dashboard'))

    if current_user.role_type == RoleType.DRIVER:
        return redirect(url_for('driver.dashboard'))

    return render_template('home.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        user = authenticate(username, password)

        if user:
            login_user(user)
            return redirect(url_for('auth.home'))

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        role = "DRIVER"
        email = request.form.get('email', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')

        try:
            register_user(username, password, role, email, first_name, last_name)
            return redirect(url_for('auth.login'))
        except ValueError as e:
            return render_template(
                'register.html',
                error=str(e),
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name
            )

    return render_template('register.html')


@auth_bp.route('/about')
@login_required
def about():
    about = AboutPage.query.get(16)
    return render_template('about.html', about=about)


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/resetpassword', methods=['GET', 'POST'])
@login_required
def reset_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')

        try:
            reset_user_password(
                current_user,
                current_password,
                new_password,
            )
            return redirect(url_for('auth.home'))
        except ValueError as e:
            return render_template('password_reset.html', error=str(e))

    return render_template('password_reset.html')
