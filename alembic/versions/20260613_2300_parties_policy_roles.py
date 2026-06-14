"""parties + policy_roles

Renames customers -> parties (the identity master), adds party_type, replaces
policies.customer_id with a policy_roles table (owner / insured / beneficiary),
and adds a sequence for policy numbers.

Revision ID: parties_policy_roles
Revises: 1caecab7bdde
Create Date: 2026-06-13 23:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "parties_policy_roles"
down_revision: Union[str, None] = "1caecab7bdde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- customers -> parties (rename table + its constraints/indexes) ---
    op.rename_table("customers", "parties")
    op.execute("ALTER INDEX ix_customers_external_ref RENAME TO ix_parties_external_ref")
    op.execute("ALTER TABLE parties RENAME CONSTRAINT pk_customers TO pk_parties")
    op.execute(
        "ALTER TABLE parties RENAME CONSTRAINT ck_customers_sex_valid "
        "TO ck_parties_sex_valid"
    )
    op.add_column(
        "parties",
        sa.Column(
            "party_type",
            sa.String(length=8),
            nullable=False,
            server_default="person",
        ),
    )
    op.create_check_constraint(
        "ck_parties_party_type_valid", "parties", "party_type IN ('person','org')"
    )

    # --- policies: drop customer_id (policy <-> party now via policy_roles) ---
    op.drop_constraint(
        "fk_policies_customer_id_customers", "policies", type_="foreignkey"
    )
    op.drop_index("ix_policies_customer_id", table_name="policies")
    op.drop_column("policies", "customer_id")

    # --- policy_roles ---
    op.create_table(
        "policy_roles",
        sa.Column("policy_id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("allocation_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner','insured','beneficiary')",
            name=op.f("ck_policy_roles_role_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["party_id"],
            ["parties.id"],
            name=op.f("fk_policy_roles_party_id_parties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["policies.id"],
            name=op.f("fk_policy_roles_policy_id_policies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_roles")),
    )
    op.create_index(
        op.f("ix_policy_roles_policy_id"), "policy_roles", ["policy_id"], unique=False
    )
    op.create_index(
        op.f("ix_policy_roles_party_id"), "policy_roles", ["party_id"], unique=False
    )
    # One owner + one insured per policy; beneficiaries may repeat.
    op.create_index(
        "uq_policy_role_singleton",
        "policy_roles",
        ["policy_id", "role"],
        unique=True,
        postgresql_where=sa.text("role IN ('owner','insured')"),
    )

    # --- policy number sequence ---
    op.execute("CREATE SEQUENCE IF NOT EXISTS policy_number_seq START 1")


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS policy_number_seq")
    op.drop_index("uq_policy_role_singleton", table_name="policy_roles")
    op.drop_index(op.f("ix_policy_roles_party_id"), table_name="policy_roles")
    op.drop_index(op.f("ix_policy_roles_policy_id"), table_name="policy_roles")
    op.drop_table("policy_roles")

    # restore policies.customer_id (nullable — POC; no backfill on downgrade)
    op.add_column(
        "policies",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_policies_customer_id", "policies", ["customer_id"], unique=False
    )

    op.drop_constraint("ck_parties_party_type_valid", "parties", type_="check")
    op.drop_column("parties", "party_type")
    op.execute(
        "ALTER TABLE parties RENAME CONSTRAINT ck_parties_sex_valid "
        "TO ck_customers_sex_valid"
    )
    op.execute("ALTER TABLE parties RENAME CONSTRAINT pk_parties TO pk_customers")
    op.execute("ALTER INDEX ix_parties_external_ref RENAME TO ix_customers_external_ref")
    op.rename_table("parties", "customers")
    op.create_foreign_key(
        "fk_policies_customer_id_customers",
        "policies",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
