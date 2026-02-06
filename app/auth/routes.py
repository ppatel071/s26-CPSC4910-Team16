from flask import render_template, request, redirect, url_for

from app.auth import auth_bp
from app.auth.services import login_user, register_user

@auth_bp.route('/')  # probably should put this route somewhere else
def home():
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        success = login_user(username, password)

        if success:
            return redirect(url_for('auth.about'))

        return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form['role']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']

        register_user(username, password, role, email)
        return redirect(url_for('auth.login'))

    return render_template('register.html')

@auth_bp.route('/about')  # this route may not belong here either, just for organization
def about():
    return render_template('about.html')
