import asyncio
import logging
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, ErrorEvent
from alembic.config import Config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dishka import make_async_container
from dishka.integrations.aiogram import inject_router, setup_dishka

from alembic import command
from manashelper.bot.middlewares.action_log import ActionLogMiddleware
from manashelper.bot.middlewares.i18n import LocaleMiddleware
from manashelper.bot.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.bot.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.bot.middlewares.rate_limit import RateLimitMiddleware
from manashelper.bot.routers.advertisement import router as advertisement_router
from manashelper.bot.routers.advertisement_moderation import router as advertisement_moderation_router
from manashelper.bot.routers.food_menu import router as food_menu_router
from manashelper.bot.routers.food_menu_cleanup import router as food_menu_cleanup_router
from manashelper.bot.routers.food_menu_notifications import router as food_menu_notifications_router
from manashelper.bot.routers.lesson_search import router as lesson_search_router
from manashelper.bot.routers.locale import router as locale_router
from manashelper.bot.routers.obis import router as obis_router
from manashelper.bot.routers.settings import router as settings_router
from manashelper.bot.routers.start import router as start_router
from manashelper.bot.routers.timetable import router as timetable_router
from manashelper.bot.routers.versions import router as versions_router
from manashelper.config import get_settings
from manashelper.di import AppProvider, RequestProvider
from manashelper.jobs.advertisement import cleanup_expired_advertisements_job
from manashelper.jobs.food_menu import broadcast_dinner_menu_job, broadcast_lunch_menu_job, sync_daily_menus_job
from manashelper.jobs.obis_notification import poll_obis_notifications_job
from manashelper.jobs.scheduled_message_deletion import cleanup_scheduled_message_deletions_job
from manashelper.jobs.timetable_sync import sync_timetable_job
from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.logging_config import configure_logging
from manashelper.services.bot_commands import build_group_commands, build_private_commands
from manashelper.services.daily_menu import BISHKEK_TZ

logger = logging.getLogger(__name__)


async def setup_commands(bot: Bot) -> None:
    for locale in Locale:
        await bot.set_my_commands(
            commands=build_private_commands(locale), scope=BotCommandScopeAllPrivateChats(), language_code=locale.value
        )
        await bot.set_my_commands(
            commands=build_group_commands(locale), scope=BotCommandScopeAllGroupChats(), language_code=locale.value
        )

    # Fallback for clients whose language isn't one of the supported locales.
    await bot.set_my_commands(commands=build_private_commands(DEFAULT_LOCALE), scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(commands=build_group_commands(DEFAULT_LOCALE), scope=BotCommandScopeAllGroupChats())


def run_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


def _handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    # Last-resort net for exceptions that escape both aiogram's per-update `@dispatcher.errors()`
    # handler below and each scheduled job's own broad `except Exception` (see the `jobs` package)
    # - e.g. a bug in a fire-and-forget callback. Without this, asyncio would only print it to
    # stderr via its default handler, bypassing our file logging entirely.
    logger.error(
        "Unhandled exception in the asyncio event loop: %s", context.get("message"), exc_info=context.get("exception")
    )


async def main() -> None:
    asyncio.get_running_loop().set_exception_handler(_handle_asyncio_exception)

    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()

    # Rate-limit first, so a chat over its allowance is rejected before it even queues up
    # for the per-chat ordering lock below.
    dispatcher.message.outer_middleware(RateLimitMiddleware())
    dispatcher.callback_query.outer_middleware(RateLimitMiddleware())

    dispatcher.message.outer_middleware(PerChatOrderingMiddleware())
    dispatcher.callback_query.outer_middleware(PerChatOrderingMiddleware())

    # Inner middleware (not outer): the `private_chat_only` flag lives on the matched handler,
    # which is only resolved - and put into `data["handler"]` - once a router's filters have
    # already picked it, so this can't run any earlier than that.
    dispatcher.message.middleware(PrivateChatOnlyMiddleware())
    dispatcher.callback_query.middleware(PrivateChatOnlyMiddleware())

    # Also inner, and registered after `PrivateChatOnlyMiddleware` so it nests inside it: only
    # logs updates that actually reached a handler, not every message/callback_query sent to the
    # bot — see bot/middlewares/action_log.py.
    dispatcher.message.middleware(ActionLogMiddleware())
    dispatcher.callback_query.middleware(ActionLogMiddleware())

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> None:
        logger.error("Unhandled exception while processing an update", exc_info=event.exception)

    dispatcher.include_router(start_router)
    dispatcher.include_router(locale_router)
    dispatcher.include_router(timetable_router)
    dispatcher.include_router(lesson_search_router)
    dispatcher.include_router(food_menu_router)
    dispatcher.include_router(food_menu_notifications_router)
    dispatcher.include_router(food_menu_cleanup_router)
    dispatcher.include_router(obis_router)
    dispatcher.include_router(settings_router)
    dispatcher.include_router(versions_router)
    dispatcher.include_router(advertisement_router)
    dispatcher.include_router(advertisement_moderation_router)

    container = make_async_container(AppProvider(), RequestProvider())
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)

    # Registered after `setup_dishka` so it nests inside dishka's own container middleware and
    # can rely on `data[CONTAINER_NAME]` already holding a request-scoped container — see
    # bot/middlewares/i18n.py.
    dispatcher.message.outer_middleware(LocaleMiddleware())
    dispatcher.callback_query.outer_middleware(LocaleMiddleware())

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
    scheduler.add_job(
        cleanup_scheduled_message_deletions_job, "interval", minutes=5, args=[container, bot], next_run_time=now
    )
    scheduler.add_job(cleanup_expired_advertisements_job, "interval", hours=1, args=[container, bot], next_run_time=now)
    scheduler.start()

    await setup_commands(bot)

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    run_migrations()
    configure_logging()
    try:
        asyncio.run(main())
    except Exception:
        logger.critical("Fatal error, shutting down", exc_info=True)
        raise
