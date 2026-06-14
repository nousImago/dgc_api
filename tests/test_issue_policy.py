from datetime import date
from decimal import Decimal

from domain.party.schema import PartyRef
from domain.policy.schema import CoverageInput, PolicyIssueRequest
from services import issuance
from tests.factories import make_party, make_product, make_version


async def test_issue_with_inline_parties(session):
    p = await make_product(session, code="TL")
    await make_version(session, p, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    req = PolicyIssueRequest(
        effective_date=date(2026, 1, 1),
        owner=PartyRef(full_name="Owner A", sex="M", date_of_birth=date(1980, 1, 1)),
        insured=PartyRef(full_name="Insured B", sex="M", date_of_birth=date(1986, 1, 1)),
        coverages=[CoverageInput(product_code="TL", sum_assured=Decimal("100000"))],
    )
    policy = await issuance.issue_policy(session, req)

    assert policy.policy_number.startswith("P-")
    roles = {r.role for r in policy.roles}
    assert {"owner", "insured"} <= roles
    assert len(policy.coverages) == 1
    assert policy.coverages[0].rate_table_version_id is not None


async def test_issue_with_existing_party(session):
    p = await make_product(session, code="TL2")
    await make_version(session, p, effective_from=date(2026, 1, 1),
                       cells=[({"age": 40, "sex": "M"}, "10")])
    insured = await make_party(session, full_name="Existing", sex="M",
                               dob=date(1986, 1, 1))
    req = PolicyIssueRequest(
        effective_date=date(2026, 1, 1),
        owner=PartyRef(party_id=insured.id),
        insured=PartyRef(party_id=insured.id),
        coverages=[CoverageInput(product_code="TL2", sum_assured=Decimal("50000"))],
    )
    policy = await issuance.issue_policy(session, req)

    insured_role = next(r for r in policy.roles if r.role == "insured")
    assert insured_role.party_id == insured.id
