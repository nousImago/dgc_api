from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.schema import LoginResponse
from domain.user.model import User
from domain.user.schema import UserOut
from integrations.db.repositories import user_repo
from observability.exceptions import UnauthorizedError
from observability.logging import logger
from services import jwt_service, security


def serialize_user(user: User) -> UserOut:
    """Flatten eager-loaded roles -> permissions into a single `permissions` list."""
    permissions = sorted(
        {perm.code for role in user.roles for perm in role.permissions}
    )
    out = UserOut.model_validate(user)
    out.permissions = permissions
    return out


async def login(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> LoginResponse:
    user = await user_repo.get_by_username(session, username)
    if user is None or not user.active:
        raise UnauthorizedError("Invalid username or password")

    if not security.verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid username or password")

    user.last_login_at = datetime.now(timezone.utc)
    await user_repo.save(session, user)

    access_token = jwt_service.encode_access_token(user.id)
    refresh_token = jwt_service.encode_refresh_token(user.id)

    logger.info("user_logged_in", user_id=user.id, username=user.username)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=serialize_user(user),
    )


async def refresh(
    session: AsyncSession,
    *,
    refresh_token: str,
) -> LoginResponse:
    claims = jwt_service.decode_token(refresh_token)
    if claims.get("type") != "refresh":
        raise UnauthorizedError("Wrong token type")

    subject = claims.get("sub")
    if not subject:
        raise UnauthorizedError("Token missing subject")

    user = await user_repo.get_by_id(session, int(subject))
    if user is None or not user.active:
        raise UnauthorizedError("User not found or inactive")

    new_access = jwt_service.encode_access_token(user.id)
    new_refresh = jwt_service.encode_refresh_token(user.id)

    return LoginResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        user=serialize_user(user),
    )
