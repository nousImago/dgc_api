from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PartyBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    sex: str = Field(pattern="^[MF]$")
    date_of_birth: date
    party_type: str = Field(default="person", pattern="^(person|org)$")


class PartyCreate(PartyBase):
    # Optional — the service generates one (PTY-…) when omitted.
    external_ref: str | None = Field(default=None, max_length=64)


class PartyOut(PartyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_ref: str
    created_at: datetime
    updated_at: datetime


class PartyRef(BaseModel):
    """Inline create-or-pick: either an existing ``party_id``, or the fields to
    create a new person. Validated in services.issuance._resolve_party."""

    party_id: int | None = None
    full_name: str | None = Field(default=None, max_length=255)
    sex: str | None = Field(default=None, pattern="^[MF]$")
    date_of_birth: date | None = None
