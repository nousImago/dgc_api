from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from domain.party.model import Party
    from domain.product.model import Product
    from domain.rate.model import RateTableVersion


class Policy(IdMixin, TimestampMixin, Base):
    """The contract — one policy number, one effective date. Bundles one or more
    coverages (a base plan + optional riders). Parties relate to the policy via
    `roles` (owner / insured / beneficiary); rating reads the *insured*."""

    __tablename__ = "policies"

    policy_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")

    coverages: Mapped[list["PolicyCoverage"]] = relationship(
        back_populates="policy",
        lazy="selectin",
        order_by="PolicyCoverage.id",
        cascade="all, delete-orphan",
    )
    roles: Mapped[list["PolicyRole"]] = relationship(
        back_populates="policy",
        lazy="selectin",
        order_by="PolicyRole.id",
        cascade="all, delete-orphan",
    )


class PolicyRole(IdMixin, TimestampMixin, Base):
    """Links a party to a policy in a role. The same party can hold different
    roles across policies. One owner + one insured per policy (enforced by a
    partial unique index); beneficiaries may repeat."""

    __tablename__ = "policy_roles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner','insured','beneficiary')", name="role_valid"
        ),
        # One owner and one insured per policy; beneficiaries excluded so they
        # can repeat (future multi-beneficiary).
        Index(
            "uq_policy_role_singleton",
            "policy_id",
            "role",
            unique=True,
            postgresql_where=text("role IN ('owner','insured')"),
        ),
    )

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    party_id: Mapped[int] = mapped_column(
        ForeignKey("parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    allocation_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    policy: Mapped["Policy"] = relationship(back_populates="roles")
    party: Mapped["Party"] = relationship(lazy="selectin")

    @property
    def party_name(self) -> str:
        # party is selectin-loaded, so this is a safe sync read at serialize time.
        return self.party.full_name if self.party else ""


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
