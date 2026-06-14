from datetime import date
from decimal import Decimal

import pytest

from observability.exceptions import ValidationError
from services import rating
from tests.factories import make_product, make_version


async def test_premium_scales_linearly_with_sum_assured(session):
    product = await make_product(session)
    await make_version(
        session, product, effective_from=date(2026, 1, 1),
        cells=[({"age": 30, "sex": "M"}, "100")],
    )
    quote = await rating.quote(
        session,
        product_code="TLX",
        effective_date=date(2026, 6, 1),
        dimensions={"age": 30, "sex": "M"},
        sum_assured=Decimal("2000"),
    )
    assert quote.gross_before_discount == Decimal("100")
    assert quote.premium == Decimal("200.00")  # 100 × 2000/1000


async def test_missing_cell_raises(session):
    product = await make_product(session)
    await make_version(
        session, product, effective_from=date(2026, 1, 1),
        cells=[({"age": 30, "sex": "M"}, "100")],
    )
    with pytest.raises(ValidationError):
        await rating.quote(
            session,
            product_code="TLX",
            effective_date=date(2026, 6, 1),
            dimensions={"age": 99, "sex": "M"},
            sum_assured=Decimal("1000"),
        )
