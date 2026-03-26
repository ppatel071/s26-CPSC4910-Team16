from app.extensions import db
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer


class Product(db.Model):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    points_required: Mapped[int] = mapped_column(Integer, nullable=False)