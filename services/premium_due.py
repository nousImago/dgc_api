from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.policy.schema import (
    CustomerPremiumDue,
    PremiumDueCoverageLine,
    PremiumDuePolicy,
)
from integrations.db.repositories import customer_repo
from observability.exceptions import DGCError, NotFoundError
from services import rating

_ZERO = Decimal("0.00")


async def premium_due_for_customer(
    session: AsyncSession, customer_id: int
) -> CustomerPremiumDue:
    """The demo centrepiece: for each policy a customer holds, rate every
    coverage (base + riders) and roll up to a per-policy subtotal and a customer
    total. Age is derived at each policy's effective date. An un-rateable
    coverage (e.g. age out of table range) yields a per-line error rather than
    failing the whole rollup."""
    customer = await customer_repo.get_by_id(session, customer_id)
    if customer is None:
        raise NotFoundError(f"Unknown customer: {customer_id}")

    total_due = _ZERO
    policies_out: list[PremiumDuePolicy] = []

    for policy in customer.policies:
        policy_total = _ZERO
        lines: list[PremiumDueCoverageLine] = []
        for cov in policy.coverages:
            line = PremiumDueCoverageLine(
                product_code=cov.product.code,
                kind=cov.product.kind,
                sex=customer.sex,
                sum_assured=cov.sum_assured,
            )
            try:
                age = rating.age_last_birthday(
                    customer.date_of_birth, policy.effective_date
                )
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
                policy_total += result.premium
            except DGCError as exc:
                line.error = exc.message
            lines.append(line)

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
