from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from domain.customer.model import Customer
    from domain.product.model import Product
    from domain.rate.model import RateTableVersion


class Policy(IdMixin, TimestampMixin, Base):
    """The contract a customer buys — one policy number, one effective date.
    Bundles one or more coverages (a base plan + optional riders). A customer
    may hold the same base product on multiple policies."""

    __tablename__ = "policies"

    policy_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    customer: Mapped["Customer"] = relationship(back_populates="policies")
    coverages: Mapped[list["PolicyCoverage"]] = relationship(
        back_populates="policy",
        lazy="selectin",
        order_by="PolicyCoverage.id",
        cascade="all, delete-orphan",
    )


class PolicyCoverage(IdMixin, TimestampMixin, Base):
    """A benefit line on a policy — base or rider. Links to its own product and
    sum_assured, and freezes the rate version it was rated against. Role
    (base/rider) is read from `product.kind`. One coverage per product within a
    policy; across policies the same product may recur."""

    __tablename__ = "policy_coverages"
    __table_args__ = (
        UniqueConstraint("policy_id", "product_id", name="coverage_per_product"),
    )

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sum_assured: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    # Frozen at issue; NULL → resolve the active version live by effective date.
    rate_table_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("rate_table_versions.id", ondelete="RESTRICT")
    )

    policy: Mapped["Policy"] = relationship(back_populates="coverages")
    product: Mapped["Product"] = relationship(lazy="selectin")
    rate_table_version: Mapped["RateTableVersion | None"] = relationship(lazy="selectin")
