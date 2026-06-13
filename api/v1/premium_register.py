from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.policy.schema import PremiumRegisterPage
from services import premium_due as premium_due_service

router = APIRouter()


@router.get(
    "",
    response_model=PremiumRegisterPage,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def premium_register(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    product_code: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> PremiumRegisterPage:
    """Portfolio premium register — one row per policy with the premium due,
    plus portfolio totals. Filter by product, search by policy number / insured.
    The operational collections view for large books."""
    return await premium_due_service.premium_register(
        db, page=page, page_size=page_size, product_code=product_code, q=q
    )
