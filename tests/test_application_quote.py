from datetime import date
from decimal import Decimal

from domain.party.schema import PartyRef
from domain.policy.schema import ApplicationQuoteRequest, CoverageInput
from services import issuance
from tests.factories import make_product, make_version


async def test_application_quote_inline_insured(session):
    p = await make_product(session, code="TL")
    await make_version(session, p, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    req = ApplicationQuoteRequest(
        effective_date=date(2026, 1, 1),
        insured=PartyRef(sex="M", date_of_birth=date(1986, 1, 1)),  # age 40
        coverages=[CoverageInput(product_code="TL", sum_assured=Decimal("100000"))],
    )
    result = await issuance.quote_application(session, req)
    assert result.total == Decimal("1000.00")
    assert result.coverages[0].premium == Decimal("1000.00")


async def test_application_quote_out_of_range_yields_error(session):
    p = await make_product(session, code="TL2")
    await make_version(session, p, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    req = ApplicationQuoteRequest(
        effective_date=date(2026, 1, 1),
        insured=PartyRef(sex="M", date_of_birth=date(1950, 1, 1)),  # age 76
        coverages=[CoverageInput(product_code="TL2", sum_assured=Decimal("1000"))],
    )
    result = await issuance.quote_application(session, req)
    assert result.coverages[0].premium is None
    assert result.coverages[0].error is not None
    assert result.total == Decimal("0.00")
