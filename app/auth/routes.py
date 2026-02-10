from flask import render_template, request, redirect, url_for
from app.auth import auth_bp
from app.auth.services import authenticate, register_user
from flask_login import login_user
from flask_login import logout_user


@auth_bp.route('/')  # probably should put this route somewhere else
def home():
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = authenticate(username, password)

        if user:
            login_user(user)
            return redirect(url_for('auth.about'))

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
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
# Use @login_required to protect a route
def about():
    return render_template('about.html')

# Logs user out and redirects to home page
@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
