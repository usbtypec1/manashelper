import asyncio
import logging
import signal
from contextlib import AsyncExitStack
from typing import Any

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
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
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.feedback.provider import FeedbackProvider
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.ui_flows.presentation.admin_provider import AdminUiFlowsProvider
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.provider import TextCatalogProvider
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.telegram.commands import setup_commands
from manashelper.platform.telegram.dispatcher import create_dispatcher
from manashelper.platform.telegram.provider import TelegramPlatformProvider
from manashelper.platform.web.application import create_admin_app
from manashelper.platform.web.provider import WebPlatformProvider
from manashelper.platform.web.webhook import install_webhook

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
            TextCatalogProvider(),
            TelegramPlatformProvider(),
            WebPlatformProvider(),
            ObisProvider(),
            EdersProvider(),
            StudyWeekProvider(),
            ScheduleProvider(),
            NotificationsProvider(),
            FeedbackProvider(),
            AdvertisementsProvider(),
            StudentQuestionsProvider(),
            UiFlowsProvider(),
            AdminUiFlowsProvider(),
            UsersProvider(),
            BroadcastProvider(),
            FoodMenuProvider(),
        )
        stack.push_async_callback(container.close)

        from manashelper.modules.ui_flows.presentation.observation import ObservationCoordinator

        await (await container.get(ObservationCoordinator)).restart()
        if settings.admin_chat_id > 0:
            from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator

            await (await container.get(FlowTelegramCoordinator)).install_defaults(settings.admin_chat_id)

        dispatcher = create_dispatcher(container)
        from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
        from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator

        effect_worker = await container.get(EffectWorker)
        flow_coordinator = await container.get(FlowTelegramCoordinator)
        effect_worker.start(lambda operation_id: flow_coordinator.complete_effect(bot, operation_id))
        stack.push_async_callback(effect_worker.aclose)
        http = create_admin_app(settings, container)
        if settings.telegram_transport == "webhook":
            install_webhook(http, bot, dispatcher, settings)
            stack.push_async_callback(dispatcher.emit_shutdown, bot=bot)
            await dispatcher.emit_startup(bot=bot)
        runner = web.AppRunner(http, access_log=None, handler_cancellation=True, shutdown_timeout=30)
        # Register cleanup before setup so partial HTTP startup failures close too.
        stack.push_async_callback(runner.cleanup)
        await runner.setup()
        site = web.TCPSite(runner, settings.http_host, settings.http_port)
        await site.start()
        scheduler = create_scheduler(container, bot)
        scheduler.start()
        stack.push_async_callback(scheduler.aclose)
        stack.push_async_callback(site.stop)

        async with container() as request:
            command_texts = await (await request.get(TextCatalogService)).current()
        with i18n.use_catalog(command_texts):
            await setup_commands(bot, settings)
        if settings.telegram_transport == "polling":
            # Explicit development transport. Registration/deletion of a Telegram
            # webhook is an operator action; never discard pending updates here.
            await dispatcher.start_polling(bot, close_bot_session=False)
        else:
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
                stack.callback(loop.remove_signal_handler, sig)
            await stop.wait()


if __name__ == "__main__":
    run_migrations()
    configure_logging()
    try:
        asyncio.run(main())
    except Exception:
        logger.critical("Fatal error, shutting down", exc_info=True)
        raise
