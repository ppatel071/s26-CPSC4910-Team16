from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, DateTime, Enum, Text
from sqlalchemy.sql import func
from typing import List, TYPE_CHECKING
import datetime as dt
from app.models.enums import DriverApplicationStatus, OrderStatus

if TYPE_CHECKING:
    from app.models.users import Driver, User
    from app.models.organization import SponsorOrganization, SponsorCatalogItem


class DriverApplication(db.Model):
    __tablename__ = 'driver_applications'

    application_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.driver_id', ondelete='CASCADE'), nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'), nullable=False)
    status: Mapped[DriverApplicationStatus] = mapped_column(Enum(DriverApplicationStatus), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    decision_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.user_id', ondelete='SET NULL'))
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    driver: Mapped['Driver'] = relationship(back_populates='applications')
    organization: Mapped['SponsorOrganization'] = relationship(back_populates='applications')
    decided_by_user: Mapped['User | None'] = relationship(back_populates='applications_decided')



class PointTransaction(db.Model):
    __tablename__ = 'point_transactions'

    transaction_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.driver_id', ondelete='CASCADE'), nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'), nullable=False)
    performed_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False)
    point_change: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    driver: Mapped['Driver'] = relationship(back_populates='point_transactions')
    organization: Mapped['SponsorOrganization'] = relationship(back_populates='point_transactions')
    performed_by_user: Mapped['User'] = relationship(back_populates='point_transactions_performed')


class Order(db.Model):
    __tablename__ = 'orders'

    order_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.driver_id', ondelete='CASCADE'), nullable=False)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'), nullable=False)
    placed_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False)
    points: Mapped[int] = mapped_column(nullable=False)
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), nullable=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    driver: Mapped['Driver'] = relationship(back_populates='orders')
    organization: Mapped['SponsorOrganization'] = relationship(back_populates='orders')
    placed_by_user: Mapped['User'] = relationship(back_populates='orders_made')
    order_items: Mapped[List['OrderItem']] = relationship(back_populates='order', cascade='all, delete-orphan')


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    item_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey('orders.order_id', ondelete='CASCADE'), nullable=False)
    catalog_id: Mapped[int] = mapped_column(ForeignKey('sponsor_catalog_items.catalog_id', ondelete='RESTRICT'), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[int] = mapped_column(nullable=False)
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped['Order'] = relationship(back_populates='order_items')
    catalog_item: Mapped['SponsorCatalogItem'] = relationship(back_populates='order_items')
