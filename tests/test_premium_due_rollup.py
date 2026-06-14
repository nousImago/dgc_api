from datetime import date
from decimal import Decimal

from domain.policy.model import PolicyCoverage
from integrations.db.repositories import product_repo
from services import premium_due
from tests.factories import (
    make_party,
    make_policy_with_insured,
    make_product,
    make_version,
)


async def test_rollup_sums_base_and_rider(session):
    base = await make_product(session, code="BASE", kind="base")
    rider = await make_product(session, code="RIDER", kind="rider")
    await make_version(session, base, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    await make_version(session, rider, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "2")])
    insured = await make_party(session, full_name="Tester", sex="M",
                               dob=date(1986, 1, 1))  # age 40 at effective date
    bp = await product_repo.get_by_code(session, "BASE")
    rp = await product_repo.get_by_code(session, "RIDER")
    await make_policy_with_insured(session, insured, [
        PolicyCoverage(product_id=bp.id, sum_assured=Decimal("100000")),
        PolicyCoverage(product_id=rp.id, sum_assured=Decimal("50000")),
    ])
    party_id = insured.id

    session.expire_all()
    result = await premium_due.premium_due_for_party(session, party_id)
    pol = result.policies[0]
    premiums = {c.product_code: c.premium for c in pol.coverages}
    assert premiums["BASE"] == Decimal("1000.00")   # 10 × 100000/1000
    assert premiums["RIDER"] == Decimal("100.00")   # 2 × 50000/1000
    assert pol.premium == Decimal("1100.00")
    assert result.total_due == Decimal("1100.00")


async def test_out_of_range_coverage_yields_error_line(session):
    base = await make_product(session, code="B2")
    await make_version(session, base, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    insured = await make_party(session, full_name="Old", sex="M",
                               dob=date(1950, 1, 1))  # age 76 → out of range
    bp = await product_repo.get_by_code(session, "B2")
    await make_policy_with_insured(
        session, insured, [PolicyCoverage(product_id=bp.id, sum_assured=Decimal("1000"))]
    )
    party_id = insured.id

    session.expire_all()
    result = await premium_due.premium_due_for_party(session, party_id)
    line = result.policies[0].coverages[0]
    assert line.premium is None
    assert line.error is not None
    assert result.total_due == Decimal("0.00")
