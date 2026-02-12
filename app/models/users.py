from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Enum
from flask_login import UserMixin
import datetime as dt
import enum


class RoleType(enum.Enum):
    DRIVER = 'DRIVER'
    SPONSOR = 'SPONSOR'
    ADMIN = 'ADMIN'


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now(dt.timezone.utc), nullable=False)
    role_type: Mapped[RoleType] = mapped_column(Enum(RoleType), nullable=False)

# Driver Model

# Admin Model

# Sponsor Model