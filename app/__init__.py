import os
from flask import Flask
from sqlalchemy import inspect, text
from app.auth import auth_bp
from app.sponsor import sponsor_bp
from app.Admin import admin_bp
from app.extensions import db, login_manager
from app.driver import driver_bp


def _ensure_user_is_active_column():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'users' not in tables:
        return

    columns = {column['name'] for column in inspector.get_columns('users')}
    if 'is_active' in columns:
        return

    db.session.execute(text('ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE'))
    db.session.commit()


def _ensure_driver_application_columns():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if 'driver_applications' not in tables:
        return

    columns = {column['name'] for column in inspector.get_columns('driver_applications')}
    statements = []
    if 'full_name' not in columns:
        statements.append('ALTER TABLE driver_applications ADD COLUMN full_name VARCHAR(255)')
    if 'phone_number' not in columns:
        statements.append('ALTER TABLE driver_applications ADD COLUMN phone_number VARCHAR(50)')
    if 'address' not in columns:
        statements.append('ALTER TABLE driver_applications ADD COLUMN address VARCHAR(255)')
    if 'experience' not in columns:
        statements.append('ALTER TABLE driver_applications ADD COLUMN experience TEXT')

    if not statements:
        return

    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()


def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_URI')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    app.register_blueprint(auth_bp)
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(driver_bp, url_prefix='/driver')

    with app.app_context():
        db.create_all()
        _ensure_user_is_active_column()
        _ensure_driver_application_columns()

    return app
