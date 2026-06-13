from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from domain.base import Base, IdMixin, TimestampMixin


class RateTableVersion(IdMixin, TimestampMixin, Base):
    """An immutable, effective-dated rate set for one product, tied to a filing
    (`source_ref`). Rates never change in place — a new filing loads a new
    version. `unit_basis` is the sum-assured base the table was filed against
    (1000 here), so the engine can scale per policy without hardcoding it."""

    __tablename__ = "rate_table_versions"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_basis: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("1000")
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = open-ended (acts as +infinity in effective-date resolution).
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    cell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RateCell(IdMixin, TimestampMixin, Base):
    """One priced combination within a version (e.g. age 30 / M). `dimensions`
    keeps the raw lookup values; `dim_key` is their canonical serialisation and
    drives the exact-match lookup + per-version uniqueness. `gross_before_discount`
    is the collectible rate; the other columns are kept for audit."""

    __tablename__ = "rate_cells"
    __table_args__ = (
        UniqueConstraint("rate_table_version_id", "dim_key", name="cell_per_version"),
    )

    rate_table_version_id: Mapped[int] = mapped_column(
        ForeignKey("rate_table_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    dim_key: Mapped[str] = mapped_column(String(255), nullable=False)
    gross_before_discount: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    net_premium: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    gross_after_discount: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
