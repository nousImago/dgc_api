from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin, TimestampMixin


class Product(IdMixin, TimestampMixin, Base):
    """A sellable coverage. Base plans and riders both live here, told apart by
    `kind`. Each product declares its own rating dimensions and owns its own
    rate tables, so a rider rates exactly like a base product."""

    __tablename__ = "products"
    __table_args__ = (CheckConstraint("kind IN ('base','rider')", name="kind_valid"),)

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="base")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    dimensions: Mapped[list["ProductRatingDimension"]] = relationship(
        back_populates="product",
        lazy="selectin",
        order_by="ProductRatingDimension.position",
        cascade="all, delete-orphan",
    )


class ProductRatingDimension(IdMixin, TimestampMixin, Base):
    """Declares one rating axis a product prices on (e.g. age, sex). Adding a
    product is data + config — new rows here — never a schema migration."""

    __tablename__ = "product_rating_dimensions"
    __table_args__ = (UniqueConstraint("product_id", "name", name="dim_name"),)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # How to coerce/normalise the xlsx value and the lookup value: "int" | "str".
    data_type: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="dimensions")
