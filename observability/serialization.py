"""Tolerant Pydantic list serialization for read endpoints.

Replaces `[XOut.model_validate(x) for x in rows]` so that a single bad row
(e.g. a legacy email like `admin@dgc.local` failing `EmailStr`) doesn't
500 the entire list response. Rows that fail validation are logged at WARNING
and skipped; the caller still receives a clean list.

Use this in GET-list endpoints. Single-object endpoints should still call
`Model.model_validate(row)` directly so the failure surfaces as a 500.
"""
from __future__ import annotations

from typing import Any, Iterable, TypeVar

from pydantic import BaseModel

from observability.logging import logger

T = TypeVar("T", bound=BaseModel)


def safe_validate_list(
    model: type[T],
    rows: Iterable[Any],
    *,
    context: str | None = None,
) -> list[T]:
    """Validate each row into `model`, logging and dropping any that fail."""
    out: list[T] = []
    label = context or model.__name__
    for row in rows:
        try:
            out.append(model.model_validate(row))
        except Exception as exc:
            logger.warning(
                "validate_skipped",
                model=label,
                row_id=getattr(row, "id", None),
                error=str(exc),
            )
    return out
