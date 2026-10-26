import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from alembic.config import Config
from dishka import make_async_container

from alembic import command
from manashelper.bootstrap import load_models
from manashelper.core.config import get_settings
from manashelper.core.logging import configure_logging
from manashelper.core.provider import CoreProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.modules.advertisements.provider import AdvertisementsProvider
from manashelper.modules.broadcast.provider import BroadcastProvider
from manashelper.modules.donations.provider import DonationsProvider
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.feedback.provider import FeedbackProvider
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.telegram.commands import setup_commands
from manashelper.platform.telegram.dispatcher import create_dispatcher
from manashelper.platform.telegram.provider import TelegramPlatformProvider

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    command.upgrade(Config("alembic.ini"), "head")


def _handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    # Catch exceptions outside update handlers and scheduled jobs in the file log.
    logger.error(
        "Unhandled exception in the asyncio event loop: %s", context.get("message"), exc_info=context.get("exception")
    )


async def main() -> None:
    load_models()
    asyncio.get_running_loop().set_exception_handler(_handle_asyncio_exception)
    settings = get_settings()

    async with AsyncExitStack() as stack:
        bot = await stack.enter_async_context(
            Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        )
        container = make_async_container(
            CoreProvider(),
            TelegramPlatformProvider(),
            ObisProvider(),
            EdersProvider(),
            StudyWeekProvider(),
            ScheduleProvider(),
            NotificationsProvider(),
            FeedbackProvider(),
            AdvertisementsProvider(),
            StudentQuestionsProvider(),
            UsersProvider(),
            DonationsProvider(),
            BroadcastProvider(),
            FoodMenuProvider(),
        )
        stack.push_async_callback(container.close)

        dispatcher = create_dispatcher(container)
        scheduler = create_scheduler(container, bot)
        scheduler.start()
        stack.callback(scheduler.shutdown)

        await setup_commands(bot, settings)
        await dispatcher.start_polling(bot, close_bot_session=False)


if __name__ == "__main__":
    run_migrations()
    configure_logging()
    try:
        asyncio.run(main())
    except Exception:
        logger.critical("Fatal error, shutting down", exc_info=True)
        raise
