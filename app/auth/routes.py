from flask import render_template, request, redirect, url_for
from app.auth import auth_bp
from app.auth.services import authenticate, register_user, reset_user_password
from flask_login import login_user, logout_user, login_required, current_user
from app.models.users import RoleType

@auth_bp.route('/')  # probably should put this route somewhere else
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if current_user.role_type == RoleType.SPONSOR:
        return redirect(url_for('sponsor.dashboard'))
    if current_user.role_type == RoleType.ADMIN:
        return redirect(url_for('admin.dashboard'))
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

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
        role = request.form.get('role', '')
        email = request.form.get('email', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        try:
            register_user(username, password, role, email)
            return redirect(url_for('auth.login'))
        except ValueError as e:
            return render_template(
                'register.html',
                error=str(e),
                role=role,
                email=email,
                username=username,
            )
        
    return render_template('register.html')

@auth_bp.route('/about')  # this route may not belong here either, just for organization
@login_required
def about():
    return render_template('about.html')

# Logs user out and redirects to home page
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
