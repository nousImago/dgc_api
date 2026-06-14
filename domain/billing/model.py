from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from domain.policy.model import Policy

_ZERO = Decimal("0.00")


class PremiumSchedule(IdMixin, TimestampMixin, Base):
    """Layer ② PRE-COMPUTE — the stored premium obligation for one policy-period.

    The servicing system of record for *what is owed and when*. Amounts are
    snapshotted at generation (event at issue / batch migration) and never
    recomputed from the rate engine. `overdue` is derived at read (unpaid +
    past due), not stored. `paid_amount` / `status` are maintained when a
    payment is verified.
    """

    __tablename__ = "premium_schedule"
    __table_args__ = (
        CheckConstraint(
            "status IN ('due','partially_paid','paid','pending_verification','cancelled')",
            name="status_valid",
        ),
        UniqueConstraint("policy_id", "period_no", name="period_per_policy"),
    )

    policy_id: Mapped[int] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(8), nullable=False, default="annual")
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    rider_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="due", index=True
    )
    # Provenance: which generation run produced this row (issue / migration batch).
    source: Mapped[str | None] = mapped_column(String(64))

    payments: Mapped[list["PremiumPayment"]] = relationship(
        back_populates="schedule",
        lazy="selectin",
        order_by="PremiumPayment.id",
        cascade="all, delete-orphan",
    )
    # selectin → loading a schedule eager-loads the policy tree (roles→party,
    # coverages→product) needed to build the payer + product summary.
    policy: Mapped["Policy"] = relationship(lazy="selectin")


class PremiumPayment(IdMixin, TimestampMixin, Base):
    """Layer ① RAW — a manually recorded premium payment (§3.2.2).

    A captured operational fact, not computed. Lands as `pending`; verifying it
    updates the parent schedule's `paid_amount` / `status` (maker-checker).
    `method` is informational only — there is no gateway/processing (out of scope).
    """

    __tablename__ = "premium_payment"
    __table_args__ = (
        CheckConstraint("method IN ('cash','cheque','transfer')", name="method_valid"),
        CheckConstraint(
            "status IN ('pending','verified','rejected')", name="status_valid"
        ),
    )

    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("premium_schedule.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paid_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="transfer")
    reference_no: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    recorded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    schedule: Mapped["PremiumSchedule"] = relationship(back_populates="payments")


class PremiumForecast(IdMixin, TimestampMixin, Base):
    """Layer ② PRE-COMPUTE (materialized rollup) — due-by-month buckets.

    A real pre-compute table the API serves directly (no live aggregation).
    Batch-refreshed from `premium_schedule` (`process/refresh_rollups.py`):
    truncate + reinsert one row per month. The serve layer slices the rolling
    and calendar windows from these absolute-month rows.
    """

    __tablename__ = "premium_forecast"
    __table_args__ = (UniqueConstraint("bucket_month", name="bucket_unique"),)

    bucket_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    rider_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=_ZERO)


class PremiumCollectionsSnapshot(IdMixin, TimestampMixin, Base):
    """Layer ② PRE-COMPUTE (materialized rollup) — collections KPIs / aging.

    One row per `as_of` refresh, written by `process/refresh_rollups.py`. The
    API serves the latest snapshot to the KPI tiles. Aging snapshots are a
    standard PAS batch artifact (point-in-time, not live).
    """

    __tablename__ = "premium_collections_snapshot"
    __table_args__ = (UniqueConstraint("as_of", name="as_of_unique"),)

    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=_ZERO
    )
    overdue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overdue_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=_ZERO
    )
    due_soon_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=_ZERO
    )
    collected_mtd: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=_ZERO
    )
