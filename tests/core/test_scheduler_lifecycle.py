import asyncio
from datetime import UTC, datetime

from manashelper.jobs.scheduler import ApplicationScheduler, DrainingExecutor


async def test_scheduler_close_waits_for_cancelled_job_finalizer():
    started, finalizing, release, finalized = (asyncio.Event() for _ in range(4))

    async def job():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalizing.set()
            await release.wait()
            finalized.set()

    scheduler = ApplicationScheduler(timezone=UTC, executors={"default": DrainingExecutor()})
    scheduler.add_job(job, "date", run_date=datetime.now(UTC))
    scheduler.start()
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        closing = asyncio.create_task(scheduler.aclose())
        try:
            await asyncio.wait_for(finalizing.wait(), timeout=1)
            assert not closing.done(), "Scheduler returned while a job still held its REQUEST resources"
        finally:
            release.set()
        await asyncio.wait_for(closing, timeout=1)
        assert finalized.is_set()
        assert not scheduler.running
    finally:
        release.set()
        if scheduler.running:
            await scheduler.aclose()
