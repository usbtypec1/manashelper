from dataclasses import dataclass, field

from aiogram import Bot, Dispatcher, Router
from aiogram.methods import EditMessageReplyMarkup, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.aiogram import inject_router, setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manashelper.core.provider import CoreProvider
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.presentation.router import router as obis_router
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.student_questions.router import router as survey_router
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.ui_flows.presentation.ingress import IngressMiddleware, LegacyRoute
from manashelper.modules.ui_flows.presentation.ingress import router as ingress_router
from manashelper.modules.ui_flows.presentation.menu_router import router as flow_menu_router
from manashelper.modules.ui_flows.presentation.navigation import UiFlowNavigationMiddleware
from manashelper.modules.ui_flows.presentation.observation import UiFlowObservationMiddleware
from manashelper.modules.ui_flows.presentation.router import reply_router as flow_reply_router
from manashelper.modules.ui_flows.presentation.router import router as flow_router
from manashelper.modules.ui_flows.presentation.survey_router import router as flow_survey_router
from manashelper.modules.ui_flows.provider import UiFlowsProvider
from manashelper.modules.users.presentation.routers.locale import router as locale_router
from manashelper.modules.users.presentation.routers.theme import router as theme_router
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.provider import TextCatalogProvider
from manashelper.platform.telegram.middlewares.action_log import ActionLogMiddleware
from manashelper.platform.telegram.middlewares.after_request import AfterRequestMiddleware
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware
from manashelper.platform.telegram.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.provider import TelegramPlatformProvider
from manashelper.platform.telegram.routers.navigation import router as navigation_router
from manashelper.platform.telegram.routers.start import router as start_router
from manashelper.platform.web.provider import WebPlatformProvider


def container_for(pool, *overrides):
    class Pool(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    return make_async_container(
        CoreProvider(),
        TextCatalogProvider(),
        UsersProvider(),
        StudentQuestionsProvider(),
        ObisProvider(),
        NotificationsProvider(),
        EdersProvider(),
        StudyWeekProvider(),
        ScheduleProvider(),
        FoodMenuProvider(),
        TelegramPlatformProvider(),
        UiFlowsProvider(),
        WebPlatformProvider(),
        Pool(),
        *overrides,
    )


def dispatcher_for(container, admin_id, *, ingress=False):
    dispatcher = Dispatcher()
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(PerChatOrderingMiddleware(container))
        observer.outer_middleware(AfterRequestMiddleware())
        observer.middleware(PrivateChatOnlyMiddleware())
        observer.middleware(UiFlowNavigationMiddleware())
        observer.middleware(UiFlowObservationMiddleware())
        observer.middleware(ActionLogMiddleware())
    # Copy handler records so production module routers remain attachable and uninjected.
    for original in (
        *((ingress_router,) if ingress else ()),
        flow_reply_router,
        flow_menu_router,
        flow_survey_router,
        survey_router,
        start_router,
        locale_router,
        theme_router,
        navigation_router,
        flow_router,
        obis_router,
    ):
        if ingress and original in (flow_reply_router, flow_menu_router, flow_survey_router):
            continue
        router = Router(name="test_" + original.name)
        if ingress and original is not ingress_router:
            for name in ("message", "callback_query"):
                getattr(router, name).filter(LegacyRoute(original.name))
        for name in ("message", "callback_query"):
            for handler in getattr(original, name).handlers:
                filters = [entry.callback for entry in (handler.filters or [])]
                getattr(router, name).register(handler.callback, *filters, flags=dict(handler.flags))
        dispatcher.include_router(router)
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)
    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(LocaleMiddleware())
        if ingress:
            observer.outer_middleware(IngressMiddleware())
    return dispatcher


@dataclass
class TelegramHarness:
    bot: Bot
    dispatcher: Dispatcher
    user_id: int
    calls: list = field(default_factory=list)
    next_id: int = 1000
    network_hook: object = None

    async def respond(self, bot, method, **kwargs):
        self.calls.append(method)
        if self.network_hook is not None:
            await self.network_hook(method)
        if isinstance(method, (SendMessage, EditMessageText, EditMessageReplyMarkup)):
            self.next_id += 1
            return Message(
                message_id=method.message_id if isinstance(method, EditMessageReplyMarkup) else self.next_id,
                date=0,
                chat=Chat(id=self.user_id, type="private"),
                text=getattr(method, "text", None),
            ).as_(bot)
        return True

    async def message(self, text, update_id, *, user_id=None, chat_type="private"):
        user_id = self.user_id if user_id is None else user_id
        return await self.dispatcher.feed_update(
            self.bot,
            Update(
                update_id=update_id,
                message=Message(
                    message_id=update_id,
                    date=0,
                    chat=Chat(id=user_id, type=chat_type),
                    from_user=User(id=user_id, is_bot=False, first_name="Flow tester", language_code="en"),
                    text=text,
                ),
            ),
        )

    async def callback(self, data, message_id, update_id, *, user_id=None):
        user_id = self.user_id if user_id is None else user_id
        return await self.dispatcher.feed_update(
            self.bot,
            Update(
                update_id=update_id,
                callback_query=CallbackQuery(
                    id=f"query-{update_id}",
                    from_user=User(id=user_id, is_bot=False, first_name="Flow tester"),
                    chat_instance="test",
                    data=data,
                    message=Message(
                        message_id=message_id, date=0, chat=Chat(id=user_id, type="private"), text="Screen"
                    ),
                ),
            ),
        )
