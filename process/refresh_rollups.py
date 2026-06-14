"""Batch: materialize the premium rollups (simulation).

Rebuilds premium_forecast (due-by-month) and premium_collections_snapshot
(KPIs / aging) from the stored premium_schedule. The API serves these tables
directly — this is the batch that keeps them fresh. Stands in for a separate
orchestration repo; in production this runs on a schedule.

Run from the repo root:

    uv run python -m process.refresh_rollups
"""
import asyncio
from datetime import date

from integrations.db.session import async_session_factory
from services import premium_servicing


async def run() -> None:
    async with async_session_factory() as session:
        await premium_servicing.refresh_rollups(session, as_of=date.today())
        await session.commit()
        print("Refreshed premium rollups (forecast + collections snapshot).")


if __name__ == "__main__":
    asyncio.run(run())
