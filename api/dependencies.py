from collections.abc import Callable

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from domain.user.model import User
from integrations.db.repositories import user_repo
from integrations.db.session import get_session
from observability.exceptions import ForbiddenError, UnauthorizedError
from services.jwt_service import decode_token

# Re-exported so routes import DB sessions from one place.
get_db = get_session


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current user from the `Authorization: Bearer <jwt>` header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1]
    claims = decode_token(token)

    if claims.get("type") != "access":
        raise UnauthorizedError("Wrong token type")

    subject = claims.get("sub")
    if not subject:
        raise UnauthorizedError("Token missing subject")

    user = await user_repo.get_by_id(session, int(subject))
    if user is None or not user.active:
        raise UnauthorizedError("User not found or inactive")

    return user


def has_permission(code: str) -> Callable:
    """Dependency factory: checks the current user's roles for the given permission code.

    Admin and owner roles bypass the literal code check — they're
    seeded with `*` (every perm), and treating them as wildcard at the
    gate avoids permission drift any time a migration adds a new code
    without remembering to re-grant to admin/owner.

    Usage:
        @router.post("/products",
                     dependencies=[Depends(has_permission("product.manage"))])
        async def create_product(...): ...
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        if any(r.code in ("admin", "owner") for r in user.roles):
            return user
        for role in user.roles:
            for perm in role.permissions:
                if perm.code == code:
                    return user
        raise ForbiddenError(f"Missing permission: {code}")

    return _check


def has_any_permission(*codes: str) -> Callable:
    """Dependency factory: passes if the user holds *any* of the given codes.

    Useful when an action is reachable from multiple workflows that
    legitimately hold different permissions — e.g. a policy can be viewed
    by someone with `policy.read` or with `policy.manage`.
    """
    needed = set(codes)

    async def _check(user: User = Depends(get_current_user)) -> User:
        # Same admin/owner bypass as has_permission — see its docstring.
        if any(r.code in ("admin", "owner") for r in user.roles):
            return user
        for role in user.roles:
            for perm in role.permissions:
                if perm.code in needed:
                    return user
        raise ForbiddenError(f"Missing permission (need any of): {', '.join(sorted(needed))}")

    return _check
