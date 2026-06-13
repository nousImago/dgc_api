from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db
from domain.auth.schema import LoginRequest, LoginResponse, TokenRefreshRequest
from domain.user.model import User
from domain.user.schema import UserOut
from services import auth_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    return await auth_service.login(
        db, username=payload.username, password=payload.password
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    payload: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    return await auth_service.refresh(db, refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    _user: User = Depends(get_current_user),
) -> None:
    """Stateless JWT: logout is client-side (clear the token).

    This endpoint exists so the client has something to call and so a
    future token blacklist can hook in here without a breaking change.
    """
    return None


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return auth_service.serialize_user(current_user)
