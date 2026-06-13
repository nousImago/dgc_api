from datetime import date
from decimal import Decimal

from domain.product.model import Product, ProductRatingDimension
from domain.rate.model import RateCell, RateTableVersion
from integrations.db.repositories import product_repo, rate_repo
from services.rating import canonical_dim_key


def age_sex_dims() -> list[ProductRatingDimension]:
    return [
        ProductRatingDimension(name="age", data_type="int", position=0),
        ProductRatingDimension(name="sex", data_type="str", position=1),
    ]


async def make_product(session, code: str = "TLX", kind: str = "base") -> Product:
    product = Product(code=code, name=code, kind=kind, active=True)
    product.dimensions = age_sex_dims()
    return await product_repo.save(session, product)


async def make_version(
    session,
    product: Product,
    *,
    effective_from: date,
    effective_to: date | None = None,
    cells: list[tuple[dict, str]] | None = None,
    source_ref: str = "filing",
    unit_basis: Decimal = Decimal("1000"),
) -> RateTableVersion:
    version = await rate_repo.save_version(
        session,
        RateTableVersion(
            product_id=product.id,
            source_ref=source_ref,
            unit_basis=unit_basis,
            effective_from=effective_from,
            effective_to=effective_to,
            status="active",
            cell_count=0,
        ),
    )
    rows = [
        RateCell(
            rate_table_version_id=version.id,
            dimensions=dims,
            dim_key=canonical_dim_key(dims, product.dimensions),
            gross_before_discount=Decimal(rate),
        )
        for dims, rate in (cells or [])
    ]
    if rows:
        await rate_repo.bulk_add_cells(session, rows)
        version.cell_count = len(rows)
        await session.flush()
    return version
