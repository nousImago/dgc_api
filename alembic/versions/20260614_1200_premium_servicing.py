"""premium servicing (§3.2)

Adds the premium servicing layer: the stored obligation (premium_schedule),
manual payment capture (premium_payment), and two materialized rollups
(premium_forecast, premium_collections_snapshot) the batch refreshes and the
API serves. Also seeds the `premium.manage` permission.

Revision ID: premium_servicing
Revises: parties_policy_roles
Create Date: 2026-06-14 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "premium_servicing"
down_revision: Union[str, None] = "parties_policy_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- premium_schedule (pre-compute: the stored obligation) ---
    op.create_table(
        "premium_schedule",
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("period_no", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("frequency", sa.String(length=8), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("rider_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('due','partially_paid','paid','pending_verification','cancelled')",
            name=op.f("ck_premium_schedule_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"], ["policies.id"],
            name=op.f("fk_premium_schedule_policy_id_policies"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_premium_schedule")),
        sa.UniqueConstraint("policy_id", "period_no", name="period_per_policy"),
    )
    op.create_index(
        op.f("ix_premium_schedule_policy_id"), "premium_schedule", ["policy_id"]
    )
    op.create_index(
        op.f("ix_premium_schedule_due_date"), "premium_schedule", ["due_date"]
    )
    op.create_index(
        op.f("ix_premium_schedule_status"), "premium_schedule", ["status"]
    )

    # --- premium_payment (raw capture: manual recording) ---
    op.create_table(
        "premium_payment",
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("reference_no", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("recorded_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "method IN ('cash','cheque','transfer')",
            name=op.f("ck_premium_payment_method_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending','verified','rejected')",
            name=op.f("ck_premium_payment_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["premium_schedule.id"],
            name=op.f("fk_premium_payment_schedule_id_premium_schedule"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"],
            name=op.f("fk_premium_payment_recorded_by_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_premium_payment")),
    )
    op.create_index(
        op.f("ix_premium_payment_schedule_id"), "premium_payment", ["schedule_id"]
    )

    # --- premium_forecast (materialized rollup: due-by-month) ---
    op.create_table(
        "premium_forecast",
        sa.Column("bucket_month", sa.Date(), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("rider_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_premium_forecast")),
        sa.UniqueConstraint("bucket_month", name="bucket_unique"),
    )
    op.create_index(
        op.f("ix_premium_forecast_bucket_month"), "premium_forecast", ["bucket_month"]
    )

    # --- premium_collections_snapshot (materialized rollup: KPIs / aging) ---
    op.create_table(
        "premium_collections_snapshot",
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("total_outstanding", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("overdue_count", sa.Integer(), nullable=False),
        sa.Column("overdue_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("due_soon_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("collected_mtd", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_premium_collections_snapshot")),
        sa.UniqueConstraint("as_of", name="as_of_unique"),
    )
    op.create_index(
        op.f("ix_premium_collections_snapshot_as_of"),
        "premium_collections_snapshot", ["as_of"],
    )

    # --- seed the premium.manage permission ---
    op.execute(
        "INSERT INTO permissions (code, name, description, resource, action) "
        "VALUES ('premium.manage', 'Manage premium servicing', "
        "'Record and verify premium payments', 'premium', 'manage') "
        "ON CONFLICT (code) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code = 'premium.manage'")
    op.drop_index(
        op.f("ix_premium_collections_snapshot_as_of"),
        table_name="premium_collections_snapshot",
    )
    op.drop_table("premium_collections_snapshot")
    op.drop_index(op.f("ix_premium_forecast_bucket_month"), table_name="premium_forecast")
    op.drop_table("premium_forecast")
    op.drop_index(op.f("ix_premium_payment_schedule_id"), table_name="premium_payment")
    op.drop_table("premium_payment")
    op.drop_index(op.f("ix_premium_schedule_status"), table_name="premium_schedule")
    op.drop_index(op.f("ix_premium_schedule_due_date"), table_name="premium_schedule")
    op.drop_index(op.f("ix_premium_schedule_policy_id"), table_name="premium_schedule")
    op.drop_table("premium_schedule")
