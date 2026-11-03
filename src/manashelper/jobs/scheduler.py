from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from manashelper.core.config import get_settings
from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.advertisements.jobs import cleanup_expired_advertisements_job
from manashelper.modules.eders.jobs import poll_eders_job
from manashelper.modules.food_menu.jobs import broadcast_dinner_menu_job, broadcast_lunch_menu_job, sync_daily_menus_job
from manashelper.modules.obis.jobs import poll_obis_notifications_job
from manashelper.modules.schedule.jobs import sync_timetable_job
from manashelper.platform.telegram.outbox.jobs import cleanup_outbox_job, run_outbox_worker


def create_scheduler(container: AsyncContainer, bot: Bot) -> AsyncIOScheduler:
    # Run interval jobs immediately so startup doesn't leave data empty for an hour.
    now = datetime.now(BISHKEK_TZ)
    scheduler = AsyncIOScheduler(timezone=BISHKEK_TZ)
    scheduler.add_job(
        run_outbox_worker,
        "date",
        run_date=now,
        args=[container, bot],
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        cleanup_outbox_job,
        "interval",
        days=1,
        args=[container],
        next_run_time=now,
        max_instances=1,
        coalesce=True,
    )
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
    scheduler.add_job(cleanup_expired_advertisements_job, "interval", hours=1, args=[container, bot], next_run_time=now)

    return scheduler
