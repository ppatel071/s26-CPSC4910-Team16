import os
from flask import Flask
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
    login_manager.login_view = 'auth.login'

    app.register_blueprint(auth_bp)
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(driver_bp, url_prefix='/driver')

    with app.app_context():
        db.create_all()
        ensure_user_account_columns(app)

    return app
