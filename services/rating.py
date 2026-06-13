from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.product.model import ProductRatingDimension
from domain.rate.schema import QuoteResult
from integrations.db.repositories import product_repo, rate_repo
from observability.exceptions import NotFoundError, ValidationError


def _normalize_value(value: object, data_type: str) -> str:
    if data_type == "int":
        return str(int(value))  # type: ignore[arg-type]
    return str(value).strip().upper()


def canonical_dim_key(
    dimensions: dict,
    declared: list[ProductRatingDimension] | None = None,
) -> str:
    """Single source of truth for the rate-cell lookup key — shared by the
    loader and the engine so they can never drift. Sort dimension names; normalise
    each value by its declared data_type (int → plain int, str → upper+strip);
    join as ``name=value`` with ``|``."""
    types = {d.name: d.data_type for d in declared} if declared else {}
    parts = [
        f"{name}={_normalize_value(dimensions[name], types.get(name, 'str'))}"
        for name in sorted(dimensions)
    ]
    return "|".join(parts)


def age_last_birthday(date_of_birth: date, as_of: date) -> int:
    """Whole years from ``date_of_birth`` to ``as_of`` (age last birthday)."""
    if as_of < date_of_birth:
        raise ValidationError("effective_date precedes date_of_birth")
    return (
        as_of.year
        - date_of_birth.year
        - ((as_of.month, as_of.day) < (date_of_birth.month, date_of_birth.day))
    )


async def quote(
    session: AsyncSession,
    *,
    product_code: str,
    effective_date: date,
    dimensions: dict,
    sum_assured: Decimal,
) -> QuoteResult:
    """Headless table lookup: resolve the rate version effective on
    ``effective_date``, find the cell matching ``dimensions``, and scale the
    collectible (gross-before-discount) rate to ``sum_assured``. Knows nothing
    about customers or policies."""
    product = await product_repo.get_by_code(session, product_code)
    if product is None:
        raise NotFoundError(f"Unknown product: {product_code}")

    version = await rate_repo.resolve_active_version(session, product.id, effective_date)
    if version is None:
        raise ValidationError(
            f"No active rate version for {product_code} effective {effective_date}"
        )

    dim_key = canonical_dim_key(dimensions, product.dimensions)
    cell = await rate_repo.get_cell(session, version.id, dim_key)
    if cell is None:
        raise ValidationError(
            f"No rate cell for dimensions {dimensions} in {product_code}"
        )

    sa = Decimal(sum_assured)
    premium = (cell.gross_before_discount * (sa / version.unit_basis)).quantize(
        Decimal("0.01")
    )

    return QuoteResult(
        product_code=product_code,
        rate_table_version_id=version.id,
        source_ref=version.source_ref,
        dimensions=dimensions,
        gross_before_discount=cell.gross_before_discount,
        unit_basis=version.unit_basis,
        sum_assured=sa,
        premium=premium,
    )
