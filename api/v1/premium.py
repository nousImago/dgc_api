from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, has_permission
from domain.billing.schema import (
    CollectionsSummary,
    DueItemsPage,
    PaymentRecord,
    PaymentsPage,
    RecordPaymentInput,
)
from domain.user.model import User
from services import premium_servicing

router = APIRouter()


@router.get(
    "/due-items",
    response_model=DueItemsPage,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def due_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    aging: str | None = None,  # accepted for forward-compat; filtering by status for now
    product_code: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> DueItemsPage:
    """Collection Management worklist — outstanding dues across the book, payer +
    aging + status, served from the stored premium_schedule (no re-rating)."""
    return await premium_servicing.due_items(
        db, status=status, q=q, product_code=product_code, page=page, page_size=page_size
    )


@router.get(
    "/collections-summary",
    response_model=CollectionsSummary,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def collections_summary(db: AsyncSession = Depends(get_db)) -> CollectionsSummary:
    """KPI tiles — served from the latest materialized collections snapshot."""
    return await premium_servicing.collections_summary(db)


@router.get(
    "/payments",
    response_model=PaymentsPage,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PaymentsPage:
    """Payments ledger / verify queue (status=pending) — the transaction history."""
    return await premium_servicing.payments(
        db, status=status, q=q, page=page, page_size=page_size
    )


@router.post(
    "/payments",
    response_model=PaymentRecord,
    dependencies=[Depends(has_permission("premium.manage"))],
)
async def record_payment(
    payload: RecordPaymentInput,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentRecord:
    """Manually record a premium payment — lands as Pending Verification."""
    return await premium_servicing.record_payment(db, payload, user_id=user.id)


@router.post(
    "/payments/{payment_id}/verify",
    response_model=PaymentRecord,
    dependencies=[Depends(has_permission("premium.manage"))],
)
async def verify_payment(
    payment_id: int, db: AsyncSession = Depends(get_db)
) -> PaymentRecord:
    """Verify a pending payment — updates the schedule's paid amount + status."""
    return await premium_servicing.verify_payment(db, payment_id)
