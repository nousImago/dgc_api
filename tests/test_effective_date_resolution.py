from datetime import date

from integrations.db.repositories import rate_repo
from tests.factories import make_product, make_version


async def test_resolves_version_by_effective_date(session):
    product = await make_product(session)
    v1 = await make_version(
        session, product,
        effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31),
    )
    v2 = await make_version(
        session, product, effective_from=date(2026, 1, 1), effective_to=None,
    )

    async def resolve(on):
        return await rate_repo.resolve_active_version(session, product.id, on)

    assert (await resolve(date(2025, 6, 1))).id == v1.id
    assert (await resolve(date(2026, 6, 1))).id == v2.id
    # boundaries are inclusive
    assert (await resolve(date(2025, 12, 31))).id == v1.id
    assert (await resolve(date(2026, 1, 1))).id == v2.id
    # open-ended upper bound
    assert (await resolve(date(2099, 1, 1))).id == v2.id
    # before any version
    assert await resolve(date(2024, 1, 1)) is None
