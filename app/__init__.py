import os
from flask import Flask
from app.auth import auth_bp
from app.sponsor import sponsor_bp
from app.Admin import admin_bp
from app.extensions import db, login_manager
from app.driver import driver_bp


def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # type: ignore

    app.register_blueprint(auth_bp)
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(driver_bp, url_prefix='/driver')

    return app
