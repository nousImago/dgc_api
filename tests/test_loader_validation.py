from datetime import date

import pytest

from domain.product.model import Product, ProductRatingDimension
from integrations.db.repositories import product_repo
from observability.exceptions import ConflictError, ValidationError
from services.rate_loader import load_rate_table
from tests.factories import make_product

DATA = "data/Premium_Table.xlsx"


async def test_happy_path_real_xlsx_loads_132_cells(session):
    await make_product(session, code="TL_LOAD")
    version = await load_rate_table(
        session,
        product_code="TL_LOAD",
        xlsx_path=DATA,
        source_ref="filing",
        effective_from=date(2026, 1, 1),
    )
    assert version.cell_count == 132


async def test_missing_dimension_column_raises(session):
    product = Product(code="TLZ", name="z", kind="base", active=True)
    product.dimensions = [
        ProductRatingDimension(name="zone", data_type="str", position=0)
    ]
    await product_repo.save(session, product)
    with pytest.raises(ValidationError):
        await load_rate_table(
            session,
            product_code="TLZ",
            xlsx_path=DATA,
            source_ref="filing",
            effective_from=date(2026, 1, 1),
        )


async def test_overlapping_window_raises_conflict(session):
    await make_product(session, code="TL_OVL")
    await load_rate_table(
        session, product_code="TL_OVL", xlsx_path=DATA,
        source_ref="f1", effective_from=date(2026, 1, 1),
    )
    with pytest.raises(ConflictError):
        await load_rate_table(
            session, product_code="TL_OVL", xlsx_path=DATA,
            source_ref="f2", effective_from=date(2026, 6, 1),
        )
