from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from domain.policy.schema import ApplicationQuoteRequest, ApplicationQuoteResult
from domain.rate.schema import QuoteRequest, QuoteResult
from domain.user.model import User
from services import issuance, rating

router = APIRouter()


@router.post("", response_model=QuoteResult)
async def create_quote(
    payload: QuoteRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> QuoteResult:
    """Headless rating: premium for a product + dimensions + sum_assured."""
    return await rating.quote(
        db,
        product_code=payload.product_code,
        effective_date=payload.effective_date,
        dimensions=payload.dimensions,
        sum_assured=payload.sum_assured,
    )


@router.post("/application", response_model=ApplicationQuoteResult)
async def quote_application(
    payload: ApplicationQuoteRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ApplicationQuoteResult:
    """Pre-issue quote: rate proposed coverages for an insured (existing or
    inline). Persists nothing."""
    return await issuance.quote_application(db, payload)
