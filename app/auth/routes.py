from flask import render_template, request

from app.auth import auth_bp

@auth_bp.route('/')  # probably should put this route somewhere else
def home():
    return render_template('home.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        pass  # add form handling here
    return render_template('login.html')

@auth_bp.route('/register')
def register():
    return render_template('register.html')

@auth_bp.route('/about')  # this route may not belong here either, just for organization
def about():
    return render_template('about.html')
