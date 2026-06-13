from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from jose import JWTError, jwt

from config import settings
from observability.exceptions import UnauthorizedError


def _now() -> datetime:
    return datetime.now(UTC)


def _next_local_midnight_utc(now_utc: datetime) -> datetime:
    """Upcoming local midnight in JWT_ACCESS_TIMEZONE, returned as UTC.

    "Local" here is the operations timezone the org runs on, not the
    browser/server clock — ops in Bangkok want their day to end at
    Bangkok midnight regardless of where the API is hosted.
    """
    tz = ZoneInfo(settings.jwt.JWT_ACCESS_TIMEZONE)
    local_now = now_utc.astimezone(tz)
    next_midnight_local = datetime.combine(
        local_now.date() + timedelta(days=1), time(0, 0), tzinfo=tz
    )
    return next_midnight_local.astimezone(UTC)


def _expiry(now_utc: datetime, ttl_minutes: int) -> datetime:
    """Pick the token expiry: the next local midnight when the
    end-of-day cap is on, else `now + ttl_minutes`."""
    if settings.jwt.JWT_ACCESS_END_OF_DAY:
        return _next_local_midnight_utc(now_utc)
    return now_utc + timedelta(minutes=ttl_minutes)


def encode_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    now = _now()
    expire = _expiry(now, settings.jwt.JWT_ACCESS_TTL_MINUTES)
    claims: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra_claims:
        claims.update(extra_claims)
    return jwt.encode(
        claims,
        settings.jwt.JWT_SECRET,
        algorithm=settings.jwt.JWT_ALGORITHM,
    )


def encode_refresh_token(subject: str | int) -> str:
    now = _now()
    # Same end-of-day cap on the refresh token — otherwise a refresh
    # round-trip past midnight would mint a fresh access token and
    # silently extend the session into the next day.
    expire = _expiry(now, settings.jwt.JWT_REFRESH_TTL_MINUTES)
    return jwt.encode(
        {
            "sub": str(subject),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
        },
        settings.jwt.JWT_SECRET,
        algorithm=settings.jwt.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt.JWT_SECRET,
            algorithms=[settings.jwt.JWT_ALGORITHM],
        )
    except JWTError as e:
        raise UnauthorizedError("Invalid or expired token") from e
