import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from alembic.config import Config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import make_async_container
from dishka.integrations.aiogram import inject_router, setup_dishka

from alembic import command
from manashelper.bot.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.bot.routers.food_menu import router as food_menu_router
from manashelper.bot.routers.food_menu_notifications import router as food_menu_notifications_router
from manashelper.bot.routers.lesson_search import router as lesson_search_router
from manashelper.bot.routers.obis import router as obis_router
from manashelper.bot.routers.settings import router as settings_router
from manashelper.bot.routers.start import router as start_router
from manashelper.bot.routers.timetable import router as timetable_router
from manashelper.config import get_settings
from manashelper.di import AppProvider, RequestProvider
from manashelper.scheduler_jobs import (
    broadcast_dinner_menu_job,
    broadcast_lunch_menu_job,
    poll_obis_notifications_job,
    sync_daily_menus_job,
    sync_timetable_job,
)
from manashelper.services.daily_menu import BISHKEK_TZ

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()

    dispatcher.message.outer_middleware(PerChatOrderingMiddleware())
    dispatcher.callback_query.outer_middleware(PerChatOrderingMiddleware())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.error("Unhandled exception while processing an update", exc_info=event.exception)

    dispatcher.include_router(start_router)
    dispatcher.include_router(timetable_router)
    dispatcher.include_router(lesson_search_router)
    dispatcher.include_router(food_menu_router)
    dispatcher.include_router(food_menu_notifications_router)
    dispatcher.include_router(obis_router)
    dispatcher.include_router(settings_router)

    container = make_async_container(AppProvider(), RequestProvider())
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)

    # `IntervalTrigger` without an explicit `start_date` fires for the first time one full interval
    # after the job is added, not immediately (see apscheduler.triggers.interval.IntervalTrigger) —
    # pass `next_run_time` so a freshly started bot doesn't sit with empty data for up to an hour.
    now = datetime.now(BISHKEK_TZ)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_daily_menus_job, "interval", minutes=10, args=[container], next_run_time=now)
    scheduler.add_job(broadcast_lunch_menu_job, "cron", hour=11, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(broadcast_dinner_menu_job, "cron", hour=17, minute=0, timezone=BISHKEK_TZ, args=[container, bot])
    scheduler.add_job(poll_obis_notifications_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.add_job(sync_timetable_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    run_migrations()
    asyncio.run(main())
