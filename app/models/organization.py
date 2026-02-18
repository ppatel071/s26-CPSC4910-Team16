from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Enum, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from decimal import Decimal
import datetime as dt
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.users import SponsorUser, Driver
    from app.models.driver_workflow import DriverApplication, PointTransaction, Order, OrderItem


class SponsorOrganization(db.Model):
    __tablename__ = 'sponsor_organization'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    organization_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    point_value: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, server_default='0.01')
    create_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sponsor_users: Mapped[List['SponsorUser']] = relationship('SponsorUser', back_populates='organization', passive_deletes=True)
    drivers: Mapped[List['Driver']] = relationship(back_populates='organization', passive_deletes=True)
    catalog_items: Mapped[List['SponsorCatalogItem']] = relationship(back_populates='organization', cascade='all, delete-orphan')
    applications: Mapped[List['DriverApplication']] = relationship(back_populates='organization', cascade='all, delete-orphan')
    point_transactions: Mapped[List['PointTransaction']] = relationship(back_populates='organization')
    orders: Mapped[List['Order']] = relationship(back_populates='organization')


class SponsorCatalogItem(db.Model):
    __tablename__ = 'sponsor_catalog_items'

    catalog_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('sponsor_organization.organization_id', ondelete='CASCADE'), nullable=False)
    external_id: Mapped[int] = mapped_column(nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_description: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[int] = mapped_column(nullable=False)
    last_update: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    organization: Mapped[SponsorOrganization] = relationship(back_populates='catalog_items')
    order_items: Mapped[List['OrderItem']] = relationship(back_populates='catalog_item')
