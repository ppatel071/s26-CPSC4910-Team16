from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, ForeignKey, DECIMAL, Text
from sqlalchemy.sql import func
from decimal import Decimal
import datetime as dt
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.users import SponsorUser, DriverSponsorship
    from app.models.driver_workflow import DriverApplication, PointTransaction, Order, OrderItem


class SponsorOrganization(db.Model):
    __tablename__ = 'sponsor_organization'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    organization_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    point_value: Mapped[Decimal] = mapped_column(DECIMAL(10, 4), nullable=False, server_default='0.01')
    # Rules/criteria the sponsor uses to award or deduct points (story 4078 / 18136)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sponsor_users: Mapped[List['SponsorUser']] = relationship(
        'SponsorUser', back_populates='organization', passive_deletes=True
    )
    driver_sponsorships: Mapped[List['DriverSponsorship']] = relationship(
        back_populates='organization', passive_deletes=True
    )
    catalog_items: Mapped[List['SponsorCatalogItem']] = relationship(
        back_populates='organization', cascade='all, delete-orphan'
    )
    applications: Mapped[List['DriverApplication']] = relationship(
        back_populates='organization', cascade='all, delete-orphan'
    )
    point_transactions: Mapped[List['PointTransaction']] = relationship(back_populates='organization')
    orders: Mapped[List['Order']] = relationship(back_populates='organization')

    def points_for_price(self, price: Decimal | float | int | None) -> int:
        """Convert a dollar value into sponsor points using the organization's point value."""
        if price is None:
            return 0

        point_value = self.point_value or Decimal('0.01')
        if point_value <= 0:
            point_value = Decimal('0.01')

        return int(Decimal(str(price)) / point_value)


class SponsorCatalogItem(db.Model):
    __tablename__ = 'sponsor_catalog_items'

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    catalog_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey('sponsor_organization.organization_id', ondelete='CASCADE'), nullable=False
    )
    external_id: Mapped[int] = mapped_column(nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Price in dollars from the external catalog API
    price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    last_update: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped[SponsorOrganization] = relationship(back_populates='catalog_items')
    order_items: Mapped[List['OrderItem']] = relationship(back_populates='catalog_item')

    @property
    def points_required(self) -> int:
        """Convert the item's dollar price to points using the sponsor's point_value rate."""
        if not self.organization:
            return 0
        return self.organization.points_for_price(self.price)
