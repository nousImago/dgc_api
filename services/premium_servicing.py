"""Premium servicing (§3.2) — the store-and-serve layer.

Generation snapshots the premium obligation once (event at issue / batch
migration); reads serve the stored rows; the rate engine is never touched on
read. Materialized rollups (forecast, collections snapshot) are batch-refreshed
by the `process/` scripts and served directly.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from domain.billing.model import PremiumPayment, PremiumSchedule
from domain.billing.schema import (
    CollectionsSummary,
    DueItem,
    DueItemsPage,
    PaymentRecord,
    PaymentsPage,
    RecordPaymentInput,
)
from domain.policy.model import Policy
from integrations.db.repositories import billing_repo, policy_repo
from observability.exceptions import NotFoundError
from services import premium_due

_ZERO = Decimal("0.00")


# --- generation (event @issue + batch) -------------------------------------


async def generate_schedule_for_policy(
    session: AsyncSession, policy: Policy, *, as_of: date, source: str = "issue"
) -> int:
    """Snapshot a policy's annual premium into stored due records, from the
    effective date through ~12 months past `as_of`. Idempotent (skips if a
    schedule already exists). Uninsurable policies (no rate) get no schedule."""
    if await billing_repo.policy_has_schedule(session, policy.id):
        return 0

    insured = premium_due._insured_party(policy)
    total, lines, any_error = await premium_due._rate_policy(session, policy, insured)
    if any_error or total <= _ZERO:
        return 0
    base, rider = premium_due._base_rider(lines)

    horizon = premium_due._add_months(max(policy.effective_date, as_of), 12)
    count = 0
    period = 1
    while True:
        due = premium_due._add_months(policy.effective_date, 12 * (period - 1))
        if due > horizon:
            break
        await billing_repo.save_schedule(
            session,
            PremiumSchedule(
                policy_id=policy.id,
                period_no=period,
                due_date=due,
                frequency="annual",
                base_amount=base,
                rider_amount=rider,
                total_amount=total,
                paid_amount=_ZERO,
                status="due",
                source=source,
            ),
        )
        period += 1
        count += 1
    return count


async def generate_all(
    session: AsyncSession, *, as_of: date, source: str = "batch"
) -> int:
    """Batch generation over the whole in-force book (the `process/` entry)."""
    total = 0
    for policy in await policy_repo.list_all(session):
        total += await generate_schedule_for_policy(
            session, policy, as_of=as_of, source=source
        )
    return total


# --- payment recording + verification (§3.2.2 / §3.2.4) --------------------


async def record_payment(
    session: AsyncSession, payload: RecordPaymentInput, *, user_id: int
) -> PaymentRecord:
    schedule = await billing_repo.get_schedule(session, payload.schedule_id)
    if schedule is None:
        raise NotFoundError(f"Unknown premium schedule: {payload.schedule_id}")

    payment = await billing_repo.save_payment(
        session,
        PremiumPayment(
            schedule_id=schedule.id,
            paid_date=payload.paid_date,
            amount=payload.amount,
            method=payload.method,
            reference_no=payload.reference_no,
            status="pending",
            recorded_by=user_id,
            notes=payload.notes,
        ),
    )
    schedule.status = "pending_verification"
    await session.flush()
    return _payment_record(payment, schedule)


async def verify_payment(session: AsyncSession, payment_id: int) -> PaymentRecord:
    payment = await billing_repo.get_payment(session, payment_id)
    if payment is None:
        raise NotFoundError(f"Unknown payment: {payment_id}")

    payment.status = "verified"
    schedule = await billing_repo.get_schedule(session, payment.schedule_id)
    # schedule.payments is selectin-loaded and identity-mapped, so the just-set
    # payment is reflected here.
    paid = sum(
        (p.amount for p in schedule.payments if p.status == "verified"), _ZERO
    )
    schedule.paid_amount = paid
    if paid >= schedule.total_amount:
        schedule.status = "paid"
    elif paid > _ZERO:
        schedule.status = "partially_paid"
    else:
        schedule.status = "due"
    await session.flush()
    return _payment_record(payment, schedule)


# --- serve (read models over stored rows) ----------------------------------


async def due_items(
    session: AsyncSession,
    *,
    status: str | None,
    q: str | None,
    product_code: str | None,
    page: int,
    page_size: int,
) -> DueItemsPage:
    today = date.today()
    scope = status or "outstanding"
    total, rows = await billing_repo.list_due_items(
        session,
        scope=scope,
        q=q,
        product_code=product_code,
        today=today,
        page=page,
        page_size=page_size,
    )
    return DueItemsPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[_due_item(r, today) for r in rows],
    )


async def collections_summary(session: AsyncSession) -> CollectionsSummary:
    snap = await billing_repo.latest_snapshot(session)
    if snap is None:
        return CollectionsSummary()
    return CollectionsSummary(
        total_outstanding=snap.total_outstanding,
        overdue_count=snap.overdue_count,
        overdue_amount=snap.overdue_amount,
        due_soon_amount=snap.due_soon_amount,
        collected_this_month=snap.collected_mtd,
    )


async def payments(
    session: AsyncSession, *, status: str | None, q: str | None, page: int, page_size: int
) -> PaymentsPage:
    total, rows = await billing_repo.list_payments(
        session, status=status, q=q, page=page, page_size=page_size
    )
    return PaymentsPage(
        total=total,
        page=page,
        page_size=page_size,
        items=[_payment_record(p, p.schedule) for p in rows],
    )


# --- rollup refresh (batch) ------------------------------------------------


async def refresh_rollups(session: AsyncSession, *, as_of: date) -> None:
    """Materialize premium_forecast (due-by-month) + premium_collections_snapshot
    (KPIs/aging) from the stored schedule. Run from `process/refresh_rollups.py`."""
    buckets = await billing_repo.forecast_buckets(session)
    normalized = [
        (date(int(y), int(m), 1), base, rider, total)
        for (y, m, base, rider, total) in buckets
    ]
    await billing_repo.replace_forecast(session, normalized)

    soon = as_of + timedelta(days=7)
    month_start = date(as_of.year, as_of.month, 1)
    next_month = premium_due._add_months(month_start, 1)
    agg = await billing_repo.collections_aggregates(
        session, as_of, soon, month_start, next_month
    )
    await billing_repo.upsert_snapshot(session, as_of, agg)


# --- helpers ----------------------------------------------------------------


def _payer(policy: Policy):
    for role in policy.roles:
        if role.role == "owner":
            return role.party
    return None


def _product_summary(policy: Policy) -> str:
    codes = [c.product.code for c in policy.coverages]
    if not codes:
        return ""
    return codes[0] + (f" +{len(codes) - 1}" if len(codes) > 1 else "")


def _display_status(schedule: PremiumSchedule, today: date) -> str:
    if schedule.status == "due" and schedule.due_date < today:
        return "overdue"
    return schedule.status


def _due_item(schedule: PremiumSchedule, today: date) -> DueItem:
    policy = schedule.policy
    payer = _payer(policy)
    return DueItem(
        schedule_id=schedule.id,
        policy_id=policy.id,
        policy_number=policy.policy_number,
        payer_party_id=payer.id if payer else None,
        payer_name=payer.full_name if payer else "—",
        product_summary=_product_summary(policy),
        due_date=schedule.due_date,
        base_amount=schedule.base_amount,
        rider_amount=schedule.rider_amount,
        total_amount=schedule.total_amount,
        paid_amount=schedule.paid_amount,
        outstanding=schedule.total_amount - schedule.paid_amount,
        status=_display_status(schedule, today),
        days_overdue=(today - schedule.due_date).days,
    )


def _payment_record(payment: PremiumPayment, schedule: PremiumSchedule) -> PaymentRecord:
    policy = schedule.policy
    payer = _payer(policy)
    return PaymentRecord(
        payment_id=payment.id,
        schedule_id=schedule.id,
        policy_id=policy.id,
        policy_number=policy.policy_number,
        payer_name=payer.full_name if payer else "—",
        paid_date=payment.paid_date,
        amount=payment.amount,
        method=payment.method,
        reference_no=payment.reference_no,
        status=payment.status,
        recorded_by=str(payment.recorded_by) if payment.recorded_by else None,
    )
