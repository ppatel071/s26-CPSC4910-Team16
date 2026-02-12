import os
from flask import Flask
from app.auth import auth_bp
from app.extensions import db, login_manager

def create_app():
    app = Flask(__name__)

    # config setup
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    # extensions init
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login' # type: ignore
    
    # blueprint registration
    app.register_blueprint(auth_bp)
    
    return app
