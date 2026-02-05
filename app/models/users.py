from app.extensions import db
from datetime import datetime
import enum


class RoleType(enum.Enum):
    DRIVER = 'DRIVER'
    SPONSOR = 'SPONSOR'
    ADMIN = 'ADMIN'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True)
    create_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    role_type = db.Column(db.Enum(RoleType), nullable=False)

# Driver Model

# Admin Model

# Sponsor Model