from flask import *

from app.auth import auth_bp

@auth_bp.route('/')
def home():
    return render_template('home.html')

@auth_bp.route('/login')
def login():
    return render_template('login.html')

@auth_bp.route('/register')
def register():
    return render_template('register.html')

@auth_bp.route('/about')
def about():
    return render_template('about.html')
