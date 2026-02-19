# This file is for creating shared objects in one place so they can be safely imported across the app
# without circular imports while still supporting the app factory pattern.
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    from app.models.users import User
    return User.query.get(int(user_id))
