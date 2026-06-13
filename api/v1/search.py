from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from domain.user.model import User
from services.search import SearchResult, global_search

router = APIRouter()


@router.get("", response_model=SearchResult)
async def search(
    q: str = Query(""),
    limit: int = Query(8, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SearchResult:
    """Global type-ahead search: parties + policies, for the header search box."""
    return await global_search(db, q, limit)
