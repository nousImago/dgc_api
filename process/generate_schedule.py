"""Batch: generate premium schedules for all in-force policies (simulation).

Snapshots each policy's annual premium into stored premium_schedule rows. This
stands in for a separate batch/orchestration repo — the API never generates on
read. Idempotent: policies that already have a schedule are skipped.

Run from the repo root:

    uv run python -m process.generate_schedule
"""
import asyncio
from datetime import date

from integrations.db.session import async_session_factory
from services import premium_servicing


async def run() -> None:
    async with async_session_factory() as session:
        rows = await premium_servicing.generate_all(
            session, as_of=date.today(), source="batch"
        )
        await session.commit()
        print(f"Generated {rows} premium schedule rows.")


if __name__ == "__main__":
    asyncio.run(run())
