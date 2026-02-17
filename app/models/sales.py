import datetime as dt
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from app.extensions import db
from app.models.users import User
from app.models.organization import SponsorOrganization


class Sale(db.Model):
    __tablename__ = 'sales'

    sale_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(
        ForeignKey('sponsor_organization.organization_id', ondelete='RESTRICT'),
        nullable=False
    )
    driver_user_id: Mapped[int] = mapped_column(
        ForeignKey('users.user_id', ondelete='RESTRICT'),
        nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    sale_time: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    sponsor: Mapped[SponsorOrganization] = relationship('SponsorOrganization')
    driver: Mapped[User] = relationship('User')
