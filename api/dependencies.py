from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from domain.user.model import User
from integrations.db.repositories import user_repo
from integrations.db.session import get_session
from observability.exceptions import ForbiddenError, UnauthorizedError
from services.jwt_service import decode_token

# Re-exported so routes import DB sessions from one place.
get_db = get_session

# Roles that bypass center-scope filtering.
# warehouse is included because dispatch happens from a central facility —
# warehouse staff aren't tied to a specific control center but still need
# to see every pending order to fulfil it.
_BYPASS_ROLES = {"admin", "owner", "warehouse"}

# Roles that should be scoped *strictly* to their assigned install centers
# (no widening to every IC under their assigned control centers).
_INSTALLER_ROLES = {"installer_auto", "installer_build"}


@dataclass
class UserScope:
    """Resolved center scope for the current user.

    bypass=True means the user has global visibility (admin/owner).
    Otherwise, queries must be filtered to the union of control_center_ids
    and install_center_ids.
    """

    bypass: bool
    control_center_ids: list[int] = field(default_factory=list)
    install_center_ids: list[int] = field(default_factory=list)


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


def get_user_scope(user: User = Depends(get_current_user)) -> UserScope:
    """Derive the center scope from the authenticated user's assignments.

    Admins and owners bypass filtering and see all centers.
    Installers are scoped strictly to their assigned install centers — they do
    not see every job in the parent control center.
    All other roles are scoped to the union of their control centers and
    install centers.
    """
    role_codes = {r.code for r in user.roles}

    if role_codes & _BYPASS_ROLES:
        return UserScope(bypass=True)

    if role_codes & _INSTALLER_ROLES:
        return UserScope(
            bypass=False,
            control_center_ids=[],
            install_center_ids=[ic.id for ic in user.install_centers],
        )

    return UserScope(
        bypass=False,
        control_center_ids=[cc.id for cc in user.control_centers],
        install_center_ids=[ic.id for ic in user.install_centers],
    )


def resolve_cc_scope(
    scope: UserScope, requested: int | None
) -> tuple[list[int] | None, bool]:
    """Reconcile a route's `control_center_id` query param with the caller's
    UserScope. Used by Operation Finance and other CC-scoped list endpoints
    to refuse data the caller isn't entitled to.

    Returns:
        allowed_ids — the list to feed `WHERE column IN (...)`, or None
                      when the caller bypasses scoping (admin/owner).
        empty       — True when the request can't possibly match anything
                      under the caller's scope; the route should
                      short-circuit and return an empty page.
    """
    if scope.bypass:
        # Admin/owner: optionally narrow to the requested CC, otherwise no
        # scope filter.
        return ([requested] if requested is not None else None), False

    allowed = list(scope.control_center_ids)
    if not allowed:
        # User has no CC assignment — no rows are visible.
        return [], True

    if requested is not None:
        if requested in allowed:
            return [requested], False
        # Requested a CC the caller isn't assigned to — silent empty
        # mirrors the job_auto pattern (don't leak existence).
        return [], True

    return allowed, False


def has_permission(code: str) -> Callable:
    """Dependency factory: checks the current user's roles for the given permission code.

    Admin and owner roles bypass the literal code check — they're
    seeded with `*` (every perm), and treating them as wildcard at the
    gate avoids permission drift any time a migration adds a new code
    without remembering to re-grant to admin/owner.

    Usage:
        @router.post("/job-auto",
                     dependencies=[Depends(has_permission("job_auto.create"))])
        async def create_job(...): ...
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
    legitimately hold different permissions — e.g. an order attachment
    can come from `order.create` (creator uploads PO) or `order.dispatch`
    (warehouse uploads delivery proof).
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
