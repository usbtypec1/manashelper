import asyncio
from datetime import datetime
from typing import Any

from aiogram import Bot
from apscheduler.events import EVENT_SCHEDULER_SHUTDOWN
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from manashelper.core.config import get_settings
from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.advertisements.jobs import cleanup_expired_advertisements_job
from manashelper.modules.eders.jobs import poll_eders_job
from manashelper.modules.food_menu.jobs import broadcast_dinner_menu_job, broadcast_lunch_menu_job, sync_daily_menus_job
from manashelper.modules.obis.jobs import poll_obis_notifications_job
from manashelper.modules.schedule.jobs import sync_timetable_job
from manashelper.modules.ui_flows.jobs import cleanup_ui_flow_data_job
from manashelper.platform.telegram.deletions.jobs import cleanup_scheduled_message_deletions_job
from manashelper.platform.web.jobs import cleanup_admin_auth_job


class DrainingExecutor(AsyncIOExecutor):  # type: ignore[misc]  # APScheduler 3 has no type declarations.
    """APScheduler 3 cancels coroutine jobs without awaiting their finalizers."""

    def __init__(self) -> None:
        super().__init__()
        self.closing: tuple[asyncio.Future[Any], ...] = ()

    def shutdown(self, wait: bool = True) -> None:
        # Snapshot before the installed executor clears its pending collection.
        self.closing = tuple(self._pending_futures)
        super().shutdown(wait)


class ApplicationScheduler(AsyncIOScheduler):  # type: ignore[misc]  # APScheduler 3 has no type declarations.
    async def aclose(self) -> None:
        stopped = asyncio.Event()
        self.add_listener(lambda event: stopped.set(), EVENT_SCHEDULER_SHUTDOWN)
        self.shutdown(wait=False)
        await stopped.wait()
        executor = self._executors["default"]
        if isinstance(executor, DrainingExecutor):
            await asyncio.gather(*executor.closing, return_exceptions=True)


def create_scheduler(container: AsyncContainer, bot: Bot) -> ApplicationScheduler:
    # Run interval jobs immediately so startup doesn't leave data empty for an hour.
    now = datetime.now(BISHKEK_TZ)
    scheduler = ApplicationScheduler(timezone=BISHKEK_TZ, executors={"default": DrainingExecutor()})
    scheduler.add_job(sync_daily_menus_job, "interval", minutes=10, args=[container], next_run_time=now)
    scheduler.add_job(broadcast_lunch_menu_job, "cron", hour=11, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(broadcast_dinner_menu_job, "cron", hour=17, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(
        poll_obis_notifications_job,
        "interval",
        minutes=15,
        args=[container, bot],
        next_run_time=now,
        max_instances=1,
        coalesce=True,
    )
    settings = get_settings()
    if settings.eders_enabled and (eders_minutes := settings.eders_poll_minutes) is not None:
        scheduler.add_job(
            poll_eders_job,
            "interval",
            minutes=eders_minutes,
            args=[container, bot],
            next_run_time=now,
            max_instances=1,
            coalesce=True,
        )
    scheduler.add_job(sync_timetable_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.add_job(
        cleanup_scheduled_message_deletions_job, "interval", minutes=5, args=[container, bot], next_run_time=now
    )
    scheduler.add_job(cleanup_expired_advertisements_job, "interval", hours=1, args=[container, bot], next_run_time=now)

    scheduler.add_job(
        cleanup_ui_flow_data_job, "cron", hour=4, minute=15, args=[container], max_instances=1, coalesce=True
    )
    scheduler.add_job(
        cleanup_admin_auth_job, "cron", hour=4, minute=20, args=[container], max_instances=1, coalesce=True
    )
    return scheduler
