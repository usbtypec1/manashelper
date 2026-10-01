from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer

from manashelper.jobs.advertisement import cleanup_expired_advertisements_job
from manashelper.jobs.food_menu import broadcast_dinner_menu_job, broadcast_lunch_menu_job, sync_daily_menus_job
from manashelper.jobs.obis_notification import poll_obis_notifications_job
from manashelper.jobs.scheduled_message_deletion import cleanup_scheduled_message_deletions_job
from manashelper.jobs.timetable_sync import sync_timetable_job
from manashelper.services.daily_menu import BISHKEK_TZ


def create_scheduler(container: AsyncContainer, bot: Bot) -> AsyncIOScheduler:
    # Run interval jobs immediately so startup doesn't leave data empty for an hour.
    now = datetime.now(BISHKEK_TZ)
    scheduler = AsyncIOScheduler(timezone=BISHKEK_TZ)
    scheduler.add_job(sync_daily_menus_job, "interval", minutes=10, args=[container], next_run_time=now)
    scheduler.add_job(broadcast_lunch_menu_job, "cron", hour=11, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(broadcast_dinner_menu_job, "cron", hour=17, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(poll_obis_notifications_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.add_job(sync_timetable_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.add_job(
        cleanup_scheduled_message_deletions_job, "interval", minutes=5, args=[container, bot], next_run_time=now
    )
    scheduler.add_job(cleanup_expired_advertisements_job, "interval", hours=1, args=[container, bot], next_run_time=now)

    return scheduler
