from datetime import date

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.billing.model import (
    PremiumCollectionsSnapshot,
    PremiumForecast,
    PremiumPayment,
    PremiumSchedule,
)
from domain.party.model import Party
from domain.policy.model import Policy, PolicyCoverage, PolicyRole
from domain.product.model import Product

# Unpaid, still-collectable statuses (overdue is a derived subset of 'due').
OUTSTANDING = ("due", "partially_paid", "pending_verification")


# --- premium_schedule (pre-compute store) ---


async def policy_has_schedule(session: AsyncSession, policy_id: int) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(PremiumSchedule)
        .where(PremiumSchedule.policy_id == policy_id)
    )
    return (result.scalar_one() or 0) > 0


async def save_schedule(
    session: AsyncSession, schedule: PremiumSchedule
) -> PremiumSchedule:
    session.add(schedule)
    await session.flush()
    return schedule


async def get_schedule(session: AsyncSession, schedule_id: int) -> PremiumSchedule | None:
    result = await session.execute(
        select(PremiumSchedule).where(PremiumSchedule.id == schedule_id)
    )
    return result.scalar_one_or_none()


async def list_schedule_for_policy(
    session: AsyncSession, policy_id: int
) -> list[PremiumSchedule]:
    """A policy's stored dues, earliest first — the register's per-policy source."""
    result = await session.execute(
        select(PremiumSchedule)
        .where(PremiumSchedule.policy_id == policy_id)
        .order_by(PremiumSchedule.due_date, PremiumSchedule.id)
    )
    return list(result.scalars().all())


def _policy_match(q: str):
    """Match a schedule's policy by number or by the OWNER (payer) party name."""
    pattern = f"%{q}%"
    return PremiumSchedule.policy.has(
        or_(
            Policy.policy_number.ilike(pattern),
            Policy.roles.any(
                and_(
                    PolicyRole.role == "owner",
                    PolicyRole.party.has(Party.full_name.ilike(pattern)),
                )
            ),
        )
    )


def _scope_condition(scope: str, today: date):
    if scope == "all":
        return None
    if scope == "overdue":
        return and_(PremiumSchedule.status == "due", PremiumSchedule.due_date < today)
    if scope == "outstanding":
        return PremiumSchedule.status.in_(OUTSTANDING)
    return PremiumSchedule.status == scope  # an exact status


async def list_due_items(
    session: AsyncSession,
    *,
    scope: str,
    q: str | None,
    product_code: str | None,
    today: date,
    page: int,
    page_size: int,
) -> tuple[int, list[PremiumSchedule]]:
    conds = []
    sc = _scope_condition(scope, today)
    if sc is not None:
        conds.append(sc)
    if q:
        conds.append(_policy_match(q))
    if product_code:
        conds.append(
            PremiumSchedule.policy.has(
                Policy.coverages.any(
                    PolicyCoverage.product.has(Product.code == product_code)
                )
            )
        )

    count_stmt = select(func.count()).select_from(PremiumSchedule)
    stmt = select(PremiumSchedule)
    if conds:
        where = and_(*conds)
        count_stmt = count_stmt.where(where)
        stmt = stmt.where(where)

    total = (await session.execute(count_stmt)).scalar_one()
    # Oldest due first → most overdue at the top of the work queue.
    rows = (
        await session.execute(
            stmt.order_by(PremiumSchedule.due_date, PremiumSchedule.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()
    return total, list(rows)


# --- premium_payment (raw capture) ---


async def save_payment(session: AsyncSession, payment: PremiumPayment) -> PremiumPayment:
    session.add(payment)
    await session.flush()
    await session.refresh(payment)
    return payment


async def get_payment(session: AsyncSession, payment_id: int) -> PremiumPayment | None:
    result = await session.execute(
        select(PremiumPayment).where(PremiumPayment.id == payment_id)
    )
    return result.scalar_one_or_none()


async def list_payments(
    session: AsyncSession,
    *,
    status: str | None,
    q: str | None,
    page: int,
    page_size: int,
) -> tuple[int, list[PremiumPayment]]:
    conds = []
    if status:
        conds.append(PremiumPayment.status == status)
    if q:
        pattern = f"%{q}%"
        conds.append(
            PremiumPayment.schedule.has(
                PremiumSchedule.policy.has(
                    or_(
                        Policy.policy_number.ilike(pattern),
                        Policy.roles.any(
                            and_(
                                PolicyRole.role == "owner",
                                PolicyRole.party.has(Party.full_name.ilike(pattern)),
                            )
                        ),
                    )
                )
            )
        )

    count_stmt = select(func.count()).select_from(PremiumPayment)
    stmt = select(PremiumPayment)
    if conds:
        where = and_(*conds)
        count_stmt = count_stmt.where(where)
        stmt = stmt.where(where)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(PremiumPayment.paid_date.desc(), PremiumPayment.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()
    return total, list(rows)


# --- materialized rollups (batch-written, API-served) ---


async def collections_aggregates(
    session: AsyncSession, today: date, soon: date, month_start: date, next_month: date
) -> dict:
    outstanding = func.coalesce(
        func.sum(PremiumSchedule.total_amount - PremiumSchedule.paid_amount), 0
    )
    total_outstanding = (
        await session.execute(
            select(outstanding).where(PremiumSchedule.status.in_(OUTSTANDING))
        )
    ).scalar_one()
    overdue_count, overdue_amount = (
        await session.execute(
            select(func.count(), outstanding).where(
                and_(PremiumSchedule.status == "due", PremiumSchedule.due_date < today)
            )
        )
    ).one()
    due_soon = (
        await session.execute(
            select(outstanding).where(
                and_(
                    PremiumSchedule.status == "due",
                    PremiumSchedule.due_date >= today,
                    PremiumSchedule.due_date < soon,
                )
            )
        )
    ).scalar_one()
    collected = (
        await session.execute(
            select(func.coalesce(func.sum(PremiumPayment.amount), 0)).where(
                and_(
                    PremiumPayment.status == "verified",
                    PremiumPayment.paid_date >= month_start,
                    PremiumPayment.paid_date < next_month,
                )
            )
        )
    ).scalar_one()
    return {
        "total_outstanding": total_outstanding,
        "overdue_count": overdue_count or 0,
        "overdue_amount": overdue_amount,
        "due_soon_amount": due_soon,
        "collected_mtd": collected,
    }


async def forecast_buckets(session: AsyncSession) -> list:
    """Sum scheduled premium by (year, month) — the materialized due-by-month
    source. Grouping by extracted parts of the Date avoids the timezone shift
    that `date_trunc` (a timestamp) introduces."""
    year = func.extract("year", PremiumSchedule.due_date)
    month = func.extract("month", PremiumSchedule.due_date)
    stmt = (
        select(
            year.label("y"),
            month.label("m"),
            func.sum(PremiumSchedule.base_amount),
            func.sum(PremiumSchedule.rider_amount),
            func.sum(PremiumSchedule.total_amount),
        )
        .group_by(year, month)
        .order_by(year, month)
    )
    return list((await session.execute(stmt)).all())


async def replace_forecast(session: AsyncSession, buckets: list[tuple]) -> None:
    await session.execute(delete(PremiumForecast))
    for bucket_month, base, rider, total in buckets:
        session.add(
            PremiumForecast(
                bucket_month=bucket_month,
                base_amount=base,
                rider_amount=rider,
                total_amount=total,
            )
        )
    await session.flush()


async def upsert_snapshot(session: AsyncSession, as_of: date, agg: dict) -> None:
    await session.execute(
        delete(PremiumCollectionsSnapshot).where(
            PremiumCollectionsSnapshot.as_of == as_of
        )
    )
    session.add(PremiumCollectionsSnapshot(as_of=as_of, **agg))
    await session.flush()


async def latest_snapshot(session: AsyncSession) -> PremiumCollectionsSnapshot | None:
    result = await session.execute(
        select(PremiumCollectionsSnapshot)
        .order_by(PremiumCollectionsSnapshot.as_of.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_forecast(session: AsyncSession) -> list[PremiumForecast]:
    result = await session.execute(
        select(PremiumForecast).order_by(PremiumForecast.bucket_month)
    )
    return list(result.scalars().all())


async def daily_due(session: AsyncSession, week_start: date, week_end: date) -> list:
    """Sum scheduled premium by due_date within [week_start, week_end). A narrow
    live aggregation over the stored schedule (no re-rating); grouping on the
    Date column directly is timezone-safe."""
    d = PremiumSchedule.due_date
    stmt = (
        select(
            d.label("d"),
            func.sum(PremiumSchedule.base_amount),
            func.sum(PremiumSchedule.rider_amount),
            func.sum(PremiumSchedule.total_amount),
        )
        .where(and_(d >= week_start, d < week_end))
        .group_by(d)
        .order_by(d)
    )
    return list((await session.execute(stmt)).all())
