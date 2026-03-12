from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
import datetime as dt


class DriverApplicationForm(db.Model):
    __tablename__ = "driver_application_form"

    application_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id", ondelete="CASCADE"),
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    experience: Mapped[str] = mapped_column(Text, nullable=False)

    create_time: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )