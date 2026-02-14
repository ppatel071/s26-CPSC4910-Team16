from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Enum, ForeignKey, DECIMAL
from sqlalchemy.sql import func
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

    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    role_type: Mapped[RoleType] = mapped_column(Enum(RoleType), nullable=False)


# Driver Model


class SponsorUser(db.Model):
    __tablename__ = 'sponsor_users'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    sponsor_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'),nullable=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = relationship('User', backref='sponsor_user', passive_deletes=True)
    organization = relationship('SponsorOrganization', back_populates='sponsor_users', passive_deletes=True)


class SponsorOrganization(db.Model):
    __tablename__ = 'sponsor_organization'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    organization_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    point_value: Mapped[float] = mapped_column(DECIMAL(10, 4), nullable=False, server_default='0.01')
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sponsor_users = relationship('SponsorUser', back_populates='organization', passive_deletes=True)
