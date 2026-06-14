from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from domain.party.model import Party
from domain.party.schema import PartyRef
from domain.policy.model import Policy, PolicyCoverage, PolicyRole
from domain.policy.schema import (
    ApplicationQuoteRequest,
    ApplicationQuoteResult,
    PolicyIssueRequest,
    PremiumDueCoverageLine,
)
from integrations.db.repositories import party_repo, policy_repo, product_repo, rate_repo
from observability.exceptions import DGCError, NotFoundError, ValidationError
from services import premium_servicing, rating

_ZERO = Decimal("0.00")


def new_external_ref() -> str:
    return f"PTY-{uuid4().hex[:12].upper()}"


async def _build_coverage(
    session: AsyncSession, product_code: str, sum_assured: Decimal, effective_date
) -> PolicyCoverage:
    """Resolve the product, freeze the active rate version at the effective date.
    The single definition of coverage creation, reused by the seed script."""
    product = await product_repo.get_by_code(session, product_code)
    if product is None:
        raise NotFoundError(f"Unknown product: {product_code}")
    version = await rate_repo.resolve_active_version(session, product.id, effective_date)
    return PolicyCoverage(
        product_id=product.id,
        sum_assured=Decimal(sum_assured),
        rate_table_version_id=version.id if version else None,
    )


async def _resolve_party(session: AsyncSession, ref: PartyRef) -> Party:
    """Inline create-or-pick: an existing party_id, or a new person."""
    if ref.party_id is not None:
        party = await party_repo.get_by_id(session, ref.party_id)
        if party is None:
            raise NotFoundError(f"Unknown party: {ref.party_id}")
        return party
    if not (ref.full_name and ref.sex and ref.date_of_birth):
        raise ValidationError(
            "Party requires party_id, or full_name + sex + date_of_birth"
        )
    return await party_repo.save(
        session,
        Party(
            external_ref=new_external_ref(),
            full_name=ref.full_name,
            sex=ref.sex,
            date_of_birth=ref.date_of_birth,
            party_type="person",
        ),
    )


async def issue_policy(session: AsyncSession, payload: PolicyIssueRequest) -> Policy:
    """Create a policy with its coverages (rate versions frozen) and party roles
    in one transaction (the request session, which commits at request end)."""
    owner = await _resolve_party(session, payload.owner)
    insured = await _resolve_party(session, payload.insured)
    beneficiary = (
        await _resolve_party(session, payload.beneficiary)
        if payload.beneficiary
        else None
    )

    coverages = [
        await _build_coverage(
            session, c.product_code, c.sum_assured, payload.effective_date
        )
        for c in payload.coverages
    ]

    policy = Policy(
        policy_number=await policy_repo.next_policy_number(session),
        effective_date=payload.effective_date,
        status="active",
    )
    policy.coverages = coverages
    policy.roles = [
        PolicyRole(party_id=owner.id, role="owner"),
        PolicyRole(party_id=insured.id, role="insured"),
    ]
    if beneficiary is not None:
        policy.roles.append(PolicyRole(party_id=beneficiary.id, role="beneficiary"))

    await policy_repo.save_policy(session, policy)
    # Re-fetch so roles→party and coverages→product are eagerly loaded.
    fresh = await policy_repo.get_by_id(session, policy.id)
    # Event-driven generation: snapshot the premium schedule at issue (§3.2).
    await premium_servicing.generate_schedule_for_policy(
        session, fresh, as_of=date.today(), source="issue"
    )
    return fresh


async def quote_application(
    session: AsyncSession, payload: ApplicationQuoteRequest
) -> ApplicationQuoteResult:
    """Rate proposed coverages for an insured (existing or inline) without
    persisting anything — the pre-issue quote."""
    if payload.insured.party_id is not None:
        party = await party_repo.get_by_id(session, payload.insured.party_id)
        if party is None:
            raise NotFoundError(f"Unknown party: {payload.insured.party_id}")
        sex, dob = party.sex, party.date_of_birth
    elif payload.insured.sex and payload.insured.date_of_birth:
        sex, dob = payload.insured.sex, payload.insured.date_of_birth
    else:
        raise ValidationError("insured requires party_id, or sex + date_of_birth")

    total = _ZERO
    lines: list[PremiumDueCoverageLine] = []
    for c in payload.coverages:
        product = await product_repo.get_by_code(session, c.product_code)
        line = PremiumDueCoverageLine(
            product_code=c.product_code,
            kind=product.kind if product else "base",
            sex=sex,
            sum_assured=Decimal(c.sum_assured),
        )
        try:
            age = rating.age_last_birthday(dob, payload.effective_date)
            line.age = age
            result = await rating.quote(
                session,
                product_code=c.product_code,
                effective_date=payload.effective_date,
                dimensions={"age": age, "sex": sex},
                sum_assured=c.sum_assured,
            )
            line.gross_before_discount = result.gross_before_discount
            line.premium = result.premium
            total += result.premium
        except DGCError as exc:
            line.error = exc.message
        lines.append(line)

    return ApplicationQuoteResult(total=total, coverages=lines)
