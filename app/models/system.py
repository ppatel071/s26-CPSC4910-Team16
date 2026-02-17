from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
import datetime as dt
from typing import Optional, TYPE_CHECKING
from app.models.enums import NotificationCategory

if TYPE_CHECKING:
    from app.models.users import User, Driver


class Notification(db.Model):
    __tablename__ = 'notifications'

    notification_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.driver_id', ondelete='CASCADE'), nullable=False)
    issued_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.user_id', ondelete='SET NULL'))
    category: Mapped[NotificationCategory] = mapped_column(Enum(NotificationCategory), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    driver: Mapped['Driver'] = relationship(back_populates='notifications')
    issued_by_user: Mapped[Optional['User']] = relationship(back_populates='issued_notifications')


class AboutPage(db.Model):
    __tablename__ = 'about_page'

    team_num: Mapped[int] = mapped_column(primary_key=True)
    sprint_num: Mapped[int] = mapped_column(nullable=False)
    release_date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_description: Mapped[str] = mapped_column(String(255), nullable=False)
    last_update: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
