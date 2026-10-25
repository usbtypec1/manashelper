import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent
from dishka import AsyncContainer
from dishka.integrations.aiogram import inject_router, setup_dishka

from manashelper.modules.advertisements.presentation.advertisement import router as advertisement_router
from manashelper.modules.advertisements.presentation.advertisement_contact import router as advertisement_contact_router
from manashelper.modules.advertisements.presentation.advertisement_moderation import (
    router as advertisement_moderation_router,
)
from manashelper.modules.broadcast.router import router as broadcast_router
from manashelper.modules.donations.router import router as donations_router
from manashelper.modules.eders.presentation.router import router as eders_router
from manashelper.modules.feedback.router import router as feedback_router
from manashelper.modules.food_menu.presentation.routers.food_menu import router as food_menu_router
from manashelper.modules.food_menu.presentation.routers.food_menu_cleanup import router as food_menu_cleanup_router
from manashelper.modules.food_menu.presentation.routers.food_menu_notifications import (
    router as food_menu_notifications_router,
)
from manashelper.modules.notifications.router import router as notifications_router
from manashelper.modules.obis.presentation.router import router as obis_router
from manashelper.modules.schedule.presentation.routers.lesson_search import router as lesson_search_router
from manashelper.modules.schedule.presentation.routers.timetable import router as timetable_router
from manashelper.modules.student_questions.router import router as student_questions_router
from manashelper.modules.users.presentation.routers.locale import router as locale_router
from manashelper.modules.users.presentation.routers.phone_numbers import router as phone_numbers_router
from manashelper.modules.versions.router import router as versions_router
from manashelper.platform.telegram.middlewares.action_log import ActionLogMiddleware
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware
from manashelper.platform.telegram.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.middlewares.rate_limit import RateLimitMiddleware
from manashelper.platform.telegram.routers.settings import router as settings_router
from manashelper.platform.telegram.routers.start import router as start_router

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
        notifications_router,
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
