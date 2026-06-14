import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.party.model import Party
from domain.policy.model import Policy
from domain.policy.schema import (
    PartyPremiumDue,
    PremiumDueCoverageLine,
    PremiumDuePolicy,
    PremiumDueSchedule,
    PremiumMonthBucket,
    PremiumRegisterItem,
    PremiumRegisterPage,
)
from integrations.db.repositories import billing_repo, party_repo, policy_repo
from observability.exceptions import DGCError, NotFoundError
from services import rating

_OUTSTANDING = ("due", "partially_paid", "pending_verification")

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


def _aggregate_status(scheds: list, today: date) -> str | None:
    """The policy-level status for the register: the most urgent across its dues."""
    if not scheds:
        return None
    states = [
        "overdue" if (s.status == "due" and s.due_date < today) else s.status
        for s in scheds
    ]
    for pref in ("overdue", "pending_verification", "partially_paid", "due"):
        if pref in states:
            return pref
    return "paid" if "paid" in states else states[0]


def _representative(scheds: list):
    """The due that drives the register row — the earliest outstanding, else the
    earliest overall."""
    pool = [s for s in scheds if s.status in _OUTSTANDING] or scheds
    return min(pool, key=lambda s: s.due_date)


async def premium_register(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    product_code: str | None = None,
    q: str | None = None,
) -> PremiumRegisterPage:
    """Portfolio-wide premium register — one row per policy, read from the stored
    `premium_schedule` (§3.2 store-and-serve; no re-rating). Each row carries the
    representative due's amounts + next due date + aggregate status + the policy's
    outstanding (billed-minus-paid). Policies with no schedule (uninsurable) show
    has_error."""
    page = max(page, 1)
    page_size = max(min(page_size, 200), 1)
    today = date.today()

    policies = await policy_repo.list_filtered(session, product_code=product_code, q=q)

    items: list[PremiumRegisterItem] = []
    for policy in policies:
        insured = _insured_party(policy)
        codes = [cov.product.code for cov in policy.coverages]
        scheds = await billing_repo.list_schedule_for_policy(session, policy.id)
        common = dict(
            policy_id=policy.id,
            policy_number=policy.policy_number,
            party_id=insured.id if insured else 0,
            insured_name=insured.full_name if insured else "—",
            effective_date=policy.effective_date,
            products=_product_summary(codes),
            coverage_count=len(codes),
        )
        if not scheds:
            items.append(
                PremiumRegisterItem(
                    **common,
                    base_premium=_ZERO,
                    rider_premium=_ZERO,
                    premium_due=_ZERO,
                    has_error=True,
                    due_date=None,
                    status=None,
                    outstanding=_ZERO,
                )
            )
            continue
        rep = _representative(scheds)
        outstanding = sum(
            (s.total_amount - s.paid_amount for s in scheds if s.status in _OUTSTANDING),
            _ZERO,
        )
        items.append(
            PremiumRegisterItem(
                **common,
                base_premium=rep.base_amount,
                rider_premium=rep.rider_amount,
                premium_due=rep.total_amount,
                has_error=False,
                due_date=rep.due_date,
                status=_aggregate_status(scheds, today),
                outstanding=outstanding,
            )
        )

    items.sort(key=lambda it: it.premium_due, reverse=True)
    total_outstanding = sum((it.outstanding or _ZERO for it in items), _ZERO)

    start = (page - 1) * page_size
    return PremiumRegisterPage(
        total_policies=len(items),
        total_outstanding=total_outstanding,
        page=page,
        page_size=page_size,
        items=items[start : start + page_size],
    )


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    year = d.year + m // 12
    month = m % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _base_rider(lines: list[PremiumDueCoverageLine]) -> tuple[Decimal, Decimal]:
    base = sum((ln.premium for ln in lines if ln.kind == "base" and ln.premium), _ZERO)
    rider = sum((ln.premium for ln in lines if ln.kind == "rider" and ln.premium), _ZERO)
    return base, rider


async def premium_due_schedule(
    session: AsyncSession, as_of: date
) -> PremiumDueSchedule:
    """Premium due **per month** (base/rider/total), read from the materialized
    `premium_forecast` rollup (§3.2 store-and-serve; batch-refreshed, not live).
    Two 12-month windows sliced from the stored month buckets: a rolling window
    (last 6 + next 6 months) and the calendar year."""
    rows = await billing_repo.list_forecast(session)
    by_month = {r.bucket_month: r for r in rows}

    def window(start: date) -> list[PremiumMonthBucket]:
        out = []
        for i in range(12):
            month = _add_months(start, i)
            r = by_month.get(month)
            out.append(
                PremiumMonthBucket(
                    month=month,
                    base=r.base_amount if r else _ZERO,
                    rider=r.rider_amount if r else _ZERO,
                    total=r.total_amount if r else _ZERO,
                )
            )
        return out

    rolling_start = _add_months(date(as_of.year, as_of.month, 1), -6)
    calendar_start = date(as_of.year, 1, 1)
    return PremiumDueSchedule(
        as_of=as_of,
        rolling=window(rolling_start),
        calendar=window(calendar_start),
    )
