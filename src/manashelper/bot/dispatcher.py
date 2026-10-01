import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from dishka import AsyncContainer
from dishka.integrations.aiogram import inject_router, setup_dishka

from manashelper.bot.middlewares.action_log import ActionLogMiddleware
from manashelper.bot.middlewares.i18n import LocaleMiddleware
from manashelper.bot.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.bot.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.bot.middlewares.rate_limit import RateLimitMiddleware
from manashelper.bot.routers.advertisement import router as advertisement_router
from manashelper.bot.routers.advertisement_contact import router as advertisement_contact_router
from manashelper.bot.routers.advertisement_moderation import router as advertisement_moderation_router
from manashelper.bot.routers.broadcast import router as broadcast_router
from manashelper.bot.routers.donations import router as donations_router
from manashelper.bot.routers.eders import router as eders_router
from manashelper.bot.routers.feedback import router as feedback_router
from manashelper.bot.routers.food_menu import router as food_menu_router
from manashelper.bot.routers.food_menu_cleanup import router as food_menu_cleanup_router
from manashelper.bot.routers.food_menu_notifications import router as food_menu_notifications_router
from manashelper.bot.routers.lesson_search import router as lesson_search_router
from manashelper.bot.routers.locale import router as locale_router
from manashelper.bot.routers.obis import router as obis_router
from manashelper.bot.routers.phone_numbers import router as phone_numbers_router
from manashelper.bot.routers.settings import router as settings_router
from manashelper.bot.routers.start import router as start_router
from manashelper.bot.routers.student_questions import router as student_questions_router
from manashelper.bot.routers.timetable import router as timetable_router
from manashelper.bot.routers.versions import router as versions_router

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> None:
    logger.error("Unhandled exception while processing an update", exc_info=event.exception)


def create_dispatcher(container: AsyncContainer) -> Dispatcher:
    dispatcher = Dispatcher()

    for observer in (dispatcher.message, dispatcher.callback_query):
        # Reject excess updates before they queue for a per-chat lock.
        observer.outer_middleware(RateLimitMiddleware())
        observer.outer_middleware(PerChatOrderingMiddleware())

        # Handler flags are available only in inner middleware. Log only updates
        # that pass the private-chat check and reach a handler.
        observer.middleware(PrivateChatOnlyMiddleware())
        observer.middleware(ActionLogMiddleware())

    dispatcher.errors.register(on_error)
    dispatcher.include_routers(
        # Survey and advertisement deep links must precede handlers claiming all /start payloads.
        student_questions_router,
        advertisement_contact_router,
        start_router,
        locale_router,
        timetable_router,
        lesson_search_router,
        food_menu_router,
        food_menu_notifications_router,
        food_menu_cleanup_router,
        obis_router,
        eders_router,
        settings_router,
        donations_router,
        phone_numbers_router,
        versions_router,
        advertisement_router,
        advertisement_moderation_router,
        broadcast_router,
        feedback_router,
    )

    # Explicit injection avoids auto_inject's conflict with startup callbacks.
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)

    # Locale resolution needs Dishka's request container in middleware data.
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(LocaleMiddleware())

    return dispatcher
