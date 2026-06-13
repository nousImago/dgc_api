from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.party.model import Party
from domain.policy.model import Policy
from domain.policy.schema import (
    PartyPremiumDue,
    PremiumDueCoverageLine,
    PremiumDuePolicy,
    PremiumRegisterItem,
    PremiumRegisterPage,
)
from integrations.db.repositories import party_repo, policy_repo
from observability.exceptions import DGCError, NotFoundError
from services import rating

_ZERO = Decimal("0.00")


def _insured_party(policy: Policy) -> Party | None:
    """The party in the 'insured' role — the rating subject. None if a policy
    was somehow issued without one (surfaced as a per-line error, not a throw)."""
    for role in policy.roles:
        if role.role == "insured":
            return role.party
    return None


async def _rate_policy(
    session: AsyncSession, policy: Policy, insured: Party | None
) -> tuple[Decimal, list[PremiumDueCoverageLine], bool]:
    """Rate every coverage on a policy against the insured's age/sex (age derived
    at the policy effective date). An un-rateable coverage (or a missing insured)
    yields an error line. Returns (policy total, coverage lines, any_error)."""
    total = _ZERO
    lines: list[PremiumDueCoverageLine] = []
    any_error = False
    for cov in policy.coverages:
        line = PremiumDueCoverageLine(
            product_code=cov.product.code,
            kind=cov.product.kind,
            sex=insured.sex if insured else "",
            sum_assured=cov.sum_assured,
        )
        if insured is None:
            line.error = "No insured party on policy"
            any_error = True
            lines.append(line)
            continue
        try:
            age = rating.age_last_birthday(insured.date_of_birth, policy.effective_date)
            line.age = age
            result = await rating.quote(
                session,
                product_code=cov.product.code,
                effective_date=policy.effective_date,
                dimensions={"age": age, "sex": insured.sex},
                sum_assured=cov.sum_assured,
            )
            line.gross_before_discount = result.gross_before_discount
            line.premium = result.premium
            total += result.premium
        except DGCError as exc:
            line.error = exc.message
            any_error = True
        lines.append(line)
    return total, lines, any_error


async def premium_due_for_party(
    session: AsyncSession, party_id: int
) -> PartyPremiumDue:
    """Premium to collect on the policies where this party is the **insured**,
    broken down by policy and coverage."""
    party = await party_repo.get_by_id(session, party_id)
    if party is None:
        raise NotFoundError(f"Unknown party: {party_id}")

    policies = await policy_repo.list_for_party(session, party_id, role="insured")
    total_due = _ZERO
    policies_out: list[PremiumDuePolicy] = []
    for policy in policies:
        insured = _insured_party(policy)
        policy_total, lines, _ = await _rate_policy(session, policy, insured)
        policies_out.append(
            PremiumDuePolicy(
                policy_number=policy.policy_number,
                effective_date=policy.effective_date,
                premium=policy_total,
                coverages=lines,
            )
        )
        total_due += policy_total

    return PartyPremiumDue(
        party_id=party.id,
        full_name=party.full_name,
        total_due=total_due,
        policies=policies_out,
    )


def _product_summary(codes: list[str]) -> str:
    if not codes:
        return ""
    return codes[0] + (f" +{len(codes) - 1}" if len(codes) > 1 else "")


async def premium_register(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    product_code: str | None = None,
    q: str | None = None,
) -> PremiumRegisterPage:
    """Portfolio-wide premium register: one row per policy with the premium due,
    plus portfolio totals. Premium is computed live, so the full filtered set is
    rated, summed, and sorted in Python before paging (see
    policy_repo.list_filtered for the production materialisation note)."""
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    policies = await policy_repo.list_filtered(session, product_code=product_code, q=q)

    items: list[PremiumRegisterItem] = []
    for policy in policies:
        insured = _insured_party(policy)
        total, lines, any_error = await _rate_policy(session, policy, insured)
        codes = [cov.product.code for cov in policy.coverages]
        items.append(
            PremiumRegisterItem(
                policy_id=policy.id,
                policy_number=policy.policy_number,
                party_id=insured.id if insured else 0,
                insured_name=insured.full_name if insured else "—",
                effective_date=policy.effective_date,
                products=_product_summary(codes),
                coverage_count=len(codes),
                premium_due=total,
                has_error=any_error,
                coverages=lines,
            )
        )

    items.sort(key=lambda it: it.premium_due, reverse=True)
    total_outstanding = sum((it.premium_due for it in items), _ZERO)

    start = (page - 1) * page_size
    return PremiumRegisterPage(
        total_policies=len(items),
        total_outstanding=total_outstanding,
        page=page,
        page_size=page_size,
        items=items[start : start + page_size],
    )
