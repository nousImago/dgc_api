from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.db.repositories import party_repo, policy_repo

_MIN_CHARS = 2


class PartyHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    party_type: str
    external_ref: str


class PolicyHit(BaseModel):
    id: int
    policy_number: str
    insured_name: str


class SearchResult(BaseModel):
    parties: list[PartyHit] = []
    policies: list[PolicyHit] = []


async def global_search(
    session: AsyncSession, q: str, limit: int = 8
) -> SearchResult:
    """Type-ahead entity search across parties + policies (by name / external_ref
    / policy number / insured name). The PAS-standard 'find a record' path."""
    q = (q or "").strip()
    if len(q) < _MIN_CHARS:
        return SearchResult()

    parties = await party_repo.search(session, q, limit)
    policies = await policy_repo.list_filtered(session, q=q)

    policy_hits = [
        PolicyHit(
            id=p.id,
            policy_number=p.policy_number,
            insured_name=next(
                (r.party.full_name for r in p.roles if r.role == "insured"), "—"
            ),
        )
        for p in policies[:limit]
    ]
    return SearchResult(
        parties=[PartyHit.model_validate(x) for x in parties],
        policies=policy_hits,
    )
