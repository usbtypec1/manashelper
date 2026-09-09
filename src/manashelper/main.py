import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent
from alembic.config import Config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import inject_router, setup_dishka

from alembic import command
from manashelper.bot.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.bot.routers.food_menu import router as food_menu_router
from manashelper.bot.routers.obis import router as obis_router
from manashelper.bot.routers.start import router as start_router
from manashelper.bot.routers.timetable import router as timetable_router
from manashelper.config import get_settings
from manashelper.di import AppProvider, RequestProvider
from manashelper.services.food_menu_sync_service import FoodMenuSyncService

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


async def sync_daily_menus_job(container: AsyncContainer) -> None:
    try:
        async with container() as request_container:
            service = await request_container.get(FoodMenuSyncService)
            await service.synchronize_daily_menus()
    except Exception:
        logger.exception("Failed to synchronize daily menus")


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
    dispatcher.include_router(food_menu_router)
    dispatcher.include_router(obis_router)

    container = make_async_container(AppProvider(), RequestProvider())
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_daily_menus_job, "interval", minutes=10, args=[container])
    scheduler.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    run_migrations()
    asyncio.run(main())
