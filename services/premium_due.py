from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.customer.model import Customer
from domain.policy.model import Policy
from domain.policy.schema import (
    CustomerPremiumDue,
    PremiumDueCoverageLine,
    PremiumDuePolicy,
    PremiumRegisterItem,
    PremiumRegisterPage,
)
from integrations.db.repositories import customer_repo, policy_repo
from observability.exceptions import DGCError, NotFoundError
from services import rating

_ZERO = Decimal("0.00")


async def _rate_policy(
    session: AsyncSession, policy: Policy, customer: Customer
) -> tuple[Decimal, list[PremiumDueCoverageLine], bool]:
    """Rate every coverage on a policy. Age is derived at the policy effective
    date; an un-rateable coverage yields an error line (not an exception).
    Returns (policy premium total, coverage lines, any_error)."""
    total = _ZERO
    lines: list[PremiumDueCoverageLine] = []
    any_error = False
    for cov in policy.coverages:
        line = PremiumDueCoverageLine(
            product_code=cov.product.code,
            kind=cov.product.kind,
            sex=customer.sex,
            sum_assured=cov.sum_assured,
        )
        try:
            age = rating.age_last_birthday(customer.date_of_birth, policy.effective_date)
            line.age = age
            result = await rating.quote(
                session,
                product_code=cov.product.code,
                effective_date=policy.effective_date,
                dimensions={"age": age, "sex": customer.sex},
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


async def premium_due_for_customer(
    session: AsyncSession, customer_id: int
) -> CustomerPremiumDue:
    """Premium to collect for one customer, broken down by policy and coverage."""
    customer = await customer_repo.get_by_id(session, customer_id)
    if customer is None:
        raise NotFoundError(f"Unknown customer: {customer_id}")

    total_due = _ZERO
    policies_out: list[PremiumDuePolicy] = []
    for policy in customer.policies:
        policy_total, lines, _ = await _rate_policy(session, policy, customer)
        policies_out.append(
            PremiumDuePolicy(
                policy_number=policy.policy_number,
                effective_date=policy.effective_date,
                premium=policy_total,
                coverages=lines,
            )
        )
        total_due += policy_total

    return CustomerPremiumDue(
        customer_id=customer.id,
        full_name=customer.full_name,
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
    plus portfolio totals. The operational view for collections at scale —
    paginated, filterable by product, searchable by policy number / insured.

    Premium is computed live, so the full filtered set is rated, summed, and
    sorted in Python before paging. See policy_repo.list_filtered for the
    production materialisation note."""
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)

    policies = await policy_repo.list_filtered(
        session, product_code=product_code, q=q
    )

    items: list[PremiumRegisterItem] = []
    for policy in policies:
        customer = policy.customer
        total, lines, any_error = await _rate_policy(session, policy, customer)
        codes = [cov.product.code for cov in policy.coverages]
        items.append(
            PremiumRegisterItem(
                policy_id=policy.id,
                policy_number=policy.policy_number,
                customer_id=customer.id,
                insured_name=customer.full_name,
                effective_date=policy.effective_date,
                products=_product_summary(codes),
                coverage_count=len(codes),
                premium_due=total,
                has_error=any_error,
                coverages=lines,
            )
        )

    # Highest premium first — the collections-oriented default.
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
