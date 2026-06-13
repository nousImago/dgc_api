"""Seed demo data for the Insurance Core POC.

Run from the repo root after `alembic upgrade head`:

    uv run python -m scripts.seed_poc

Seeds a base term-life product (loaded from the real Premium Table xlsx), a
rider product with a small synthetic rate table, and a handful of customers and
policies — including a customer holding the same base product on two policies
with different riders, and one customer whose age falls outside the rate table.
"""
import asyncio
from datetime import date
from decimal import Decimal

from domain.customer.model import Customer
from domain.policy.model import Policy, PolicyCoverage
from domain.product.model import Product, ProductRatingDimension
from domain.rate.model import RateCell, RateTableVersion
from integrations.db.repositories import (
    customer_repo,
    policy_repo,
    product_repo,
    rate_repo,
)
from integrations.db.session import async_session_factory
from services.rate_loader import load_rate_table
from services.rating import canonical_dim_key

DATA_FILE = "data/Premium_Table.xlsx"
EFFECTIVE = date(2026, 1, 1)


def _dims() -> list[ProductRatingDimension]:
    return [
        ProductRatingDimension(name="age", data_type="int", position=0),
        ProductRatingDimension(name="sex", data_type="str", position=1),
    ]


async def _seed_rider(session, product: Product) -> RateTableVersion:
    """A rider with a flat per-1000 synthetic rate over age 0–65 × M/F, so any
    in-range customer rates. Demonstrates that riders use the same engine."""
    version = await rate_repo.save_version(
        session,
        RateTableVersion(
            product_id=product.id,
            source_ref="FILING-2026-ADB",
            unit_basis=Decimal("1000"),
            effective_from=EFFECTIVE,
            effective_to=None,
            status="active",
            cell_count=0,
        ),
    )
    cells: list[RateCell] = []
    for age in range(0, 66):
        for sex in ("M", "F"):
            dims = {"age": age, "sex": sex}
            cells.append(
                RateCell(
                    rate_table_version_id=version.id,
                    dimensions=dims,
                    dim_key=canonical_dim_key(dims, product.dimensions),
                    gross_before_discount=Decimal("2.00") if sex == "M" else Decimal("1.80"),
                )
            )
    await rate_repo.bulk_add_cells(session, cells)
    version.cell_count = len(cells)
    await session.flush()
    return version


async def seed() -> None:
    async with async_session_factory() as session:
        if await product_repo.get_by_code(session, "TERM_LIFE_1") is not None:
            print("Already seeded — skipping.")
            return

        # --- Base product, loaded from the real premium table ---
        base = Product(code="TERM_LIFE_1", name="Term Life 1", kind="base", active=True)
        base.dimensions = _dims()
        await product_repo.save(session, base)
        base_version = await load_rate_table(
            session,
            product_code="TERM_LIFE_1",
            xlsx_path=DATA_FILE,
            source_ref="FILING-2026-001",
            effective_from=EFFECTIVE,
        )
        print(f"Base rate version {base_version.id}: {base_version.cell_count} cells")

        # --- Rider product, synthetic rate table ---
        rider = Product(
            code="ADB_RIDER",
            name="Accidental Death Benefit Rider",
            kind="rider",
            active=True,
        )
        rider.dimensions = _dims()
        await product_repo.save(session, rider)
        rider_version = await _seed_rider(session, rider)
        print(f"Rider rate version {rider_version.id}: {rider_version.cell_count} cells")

        # --- Customers (varied DOB incl. age 0 and one out of range) ---
        async def add_customer(ref, name, sex, dob) -> Customer:
            return await customer_repo.save(
                session,
                Customer(external_ref=ref, full_name=name, sex=sex, date_of_birth=dob),
            )

        somchai = await add_customer("C001", "Somchai Jaidee", "M", date(1990, 5, 2))
        anong = await add_customer("C002", "Anong Sukjai", "F", date(1976, 3, 15))
        baby = await add_customer("C003", "Baby Noi", "M", date(2025, 7, 1))
        elder = await add_customer("C004", "Grandpa Wit", "M", date(1955, 1, 1))

        # --- Policies ---
        async def coverage(product_code: str, sum_assured: str) -> PolicyCoverage:
            product = await product_repo.get_by_code(session, product_code)
            version = await rate_repo.resolve_active_version(
                session, product.id, EFFECTIVE
            )
            return PolicyCoverage(
                product_id=product.id,
                sum_assured=Decimal(sum_assured),
                rate_table_version_id=version.id if version else None,
            )

        async def make_policy(number, customer, coverages) -> None:
            policy = Policy(
                policy_number=number,
                customer_id=customer.id,
                effective_date=EFFECTIVE,
                status="active",
            )
            policy.coverages = coverages
            await policy_repo.save_policy(session, policy)

        # Somchai holds the SAME base product on two policies, different riders.
        await make_policy(
            "P-0001",
            somchai,
            [await coverage("TERM_LIFE_1", "500000"), await coverage("ADB_RIDER", "200000")],
        )
        await make_policy(
            "P-0002",
            somchai,
            [await coverage("TERM_LIFE_1", "1000000"), await coverage("ADB_RIDER", "300000")],
        )
        await make_policy("P-0003", anong, [await coverage("TERM_LIFE_1", "800000")])
        await make_policy("P-0004", baby, [await coverage("TERM_LIFE_1", "100000")])
        # Grandpa Wit is 71 at the effective date — out of the 0–65 table range.
        await make_policy("P-0005", elder, [await coverage("TERM_LIFE_1", "100000")])

        await session.commit()
        print("Seed complete: 2 products, 4 customers, 5 policies.")


if __name__ == "__main__":
    asyncio.run(seed())
