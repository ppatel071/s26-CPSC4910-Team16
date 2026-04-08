import os
from flask import Flask, flash, redirect, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import inspect, text
from app.auth import auth_bp
from app.sponsor import sponsor_bp
from app.Admin import admin_bp
from app.extensions import db, login_manager
from app.driver import driver_bp


def ensure_user_account_columns(app: Flask) -> None:
    with app.app_context():
        inspector = inspect(db.engine)
        column_names = {column['name'] for column in inspector.get_columns('users')}
        dialect = db.engine.dialect.name

        statements: list[str] = []
        if 'failed_login_attempts' not in column_names:
            statements.append('ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER NOT NULL DEFAULT 0')
        if 'is_login_locked' not in column_names:
            statements.append('ALTER TABLE users ADD COLUMN is_login_locked BOOLEAN NOT NULL DEFAULT FALSE')
        if 'must_notify_password_reset' not in column_names:
            statements.append(
                'ALTER TABLE users ADD COLUMN must_notify_password_reset BOOLEAN NOT NULL DEFAULT FALSE'
            )
        if 'locked_at' not in column_names:
            locked_at_type = 'TIMESTAMP WITH TIME ZONE'
            if dialect in {'sqlite', 'mysql'}:
                locked_at_type = 'DATETIME'
            statements.append(f'ALTER TABLE users ADD COLUMN locked_at {locked_at_type}')

        if not statements:
            return

        with db.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


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

    @app.before_request
    def expire_idle_sponsor_impersonation():
        from app.auth.impersonation import (
            clear_sponsor_driver_impersonation,
            get_impersonator_sponsor_user_id,
            is_sponsor_driver_impersonation_active,
            is_sponsor_driver_impersonation_timed_out,
            touch_sponsor_driver_impersonation_activity,
        )
        from app.driver.services import get_sponsor_user_for_impersonation_return

        if request.endpoint == 'static':
            return None

        if not current_user.is_authenticated:
            return None

        if not is_sponsor_driver_impersonation_active():
            return None

        if is_sponsor_driver_impersonation_timed_out():
            sponsor_user_id = get_impersonator_sponsor_user_id()
            clear_sponsor_driver_impersonation()

            if sponsor_user_id is None:
                return None

            sponsor_user = get_sponsor_user_for_impersonation_return(sponsor_user_id)
            if sponsor_user is None:
                logout_user()
                flash(
                    'Your sponsor impersonation session expired, and the sponsor account could not be restored.',
                    'error',
                )
                return redirect(url_for('auth.login'))

            login_user(sponsor_user)
            flash(
                'Your sponsor impersonation session expired after 10 minutes of inactivity.',
                'info',
            )
            return redirect(url_for('sponsor.driver_management'))

        touch_sponsor_driver_impersonation_activity()
        return None

    with app.app_context():
        db.create_all()
        ensure_user_account_columns(app)

    return app
