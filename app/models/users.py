from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Enum, ForeignKey, Boolean, Integer
from sqlalchemy.sql import func
from flask_login import UserMixin
from typing import List, Optional, TYPE_CHECKING
import datetime as dt
from app.models.enums import RoleType, PasswordChangeType, DriverStatus

if TYPE_CHECKING:
    from app.models.organization import SponsorOrganization
    from app.models.driver_workflow import DriverApplication, PointTransaction, Order
    from app.models.system import Notification


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
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))

    sponsor_user: Mapped[Optional['SponsorUser']] = relationship(back_populates='user', uselist=False)
    driver: Mapped[List['Driver']] = relationship(back_populates='user', uselist=False)
    login_attempts: Mapped[List['LoginAttempt']] = relationship(back_populates='user', passive_deletes=True)
    password_changes: Mapped[List['PasswordChange']] = relationship(back_populates='user', cascade='all, delete-orphan')
    issued_notifications: Mapped[List['Notification']] = relationship(back_populates='issued_by_user')
    orders_made: Mapped[List['Order']] = relationship(back_populates='placed_by_user')
    applications_decided: Mapped[List['DriverApplication']] = relationship(back_populates='decided_by_user')
    point_transactions_performed: Mapped[List['PointTransaction']] = relationship(back_populates='performed_by_user')

    def get_id(self) -> str:
        return str(self.user_id)


class Driver(db.Model):
    __tablename__ = 'drivers'

    driver_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'), nullable=False)
    point_bal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    account_status: Mapped[DriverStatus] = mapped_column(Enum(DriverStatus), nullable=False)
    point_change_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship(back_populates='driver')
    organization: Mapped['SponsorOrganization'] = relationship('SponsorOrganization', back_populates='drivers', passive_deletes=True)
    applications: Mapped[List['DriverApplication']] = relationship(back_populates='driver', cascade='all, delete-orphan')
    point_transactions: Mapped[List['PointTransaction']] = relationship(back_populates='driver', cascade='all, delete-orphan')
    notifications: Mapped[List['Notification']] = relationship(back_populates='driver', cascade='all, delete-orphan')
    orders: Mapped[List['Order']] = relationship(back_populates='driver')


class SponsorUser(db.Model):
    __tablename__ = 'sponsor_users'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    sponsor_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False, unique=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'), nullable=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship(back_populates='sponsor_user')
    organization: Mapped['SponsorOrganization'] = relationship('SponsorOrganization', back_populates='sponsor_users', passive_deletes=True)


class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    attempt_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.user_id', ondelete='SET NULL'))
    username_attempted: Mapped[str] = mapped_column(String(255), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempt_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship(back_populates='login_attempts')


class PasswordChange(db.Model):
    __tablename__ = 'password_changes'

    pass_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    change_type: Mapped[PasswordChangeType] = mapped_column(Enum(PasswordChangeType), nullable=False)
    change_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped[User] = relationship(back_populates='password_changes')
