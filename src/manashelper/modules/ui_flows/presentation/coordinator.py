import logging
from typing import Literal

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.i18n import gettext as _
from dishka import AsyncContainer

from manashelper.localization.theme import Theme
from manashelper.modules.student_questions.flow import SURVEY_FLOW_ID, survey_document
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.demo import DEMO_FLOW_ID, demo_document
from manashelper.modules.ui_flows.menus import MAIN_MENU_ID, main_menu_document
from manashelper.modules.ui_flows.presentation.features import TelegramFlowContext, open_feature
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, validate_message
from manashelper.modules.ui_flows.presentation.sender import send_screen
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.delivery import is_permanent_recipient_error
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import ButtonEvent, EventIdentity, InputEvent, NavigationEvent
from ui_flows.domain.delivery import ScreenDelivery
from ui_flows.domain.state import ExecutionResult, RuntimeUser
from ui_flows.errors import (
    ActiveDialogError,
    DialogNotFoundError,
    FlowExecutionError,
    FlowNotFoundError,
    InvalidEventError,
    StaleEventError,
)

logger = logging.getLogger(__name__)


class FlowTelegramCoordinator:
    """APP orchestrator. Call after the update's REQUEST closes, while chat ordering is held."""

    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    @staticmethod
    async def _user(request: AsyncContainer, user_id: int) -> RuntimeUser:
        locale = await (await request.get(LocaleService)).get_locale(user_id)
        theme = await (await request.get(ThemeService)).get_theme(user_id)
        return RuntimeUser(user_id, user_id, locale.value, theme.value)

    @staticmethod
    async def _prepare(
        request: AsyncContainer, result: ExecutionResult, user: RuntimeUser, update_id: int
    ) -> ScreenDelivery:
        version = await (await request.get(FlowService)).version(result.state.flow_id, result.state.flow_version)
        policy = await request.get(FlowPolicy)
        screen = FlowRenderer().render(version.document, result, user, dict(policy.capabilities))
        if result.returned_from is not None:
            previous = result.returned_from
            source = await (await request.get(FlowService)).version(previous.flow_id, previous.flow_version)
            ending = next(node for node in source.document.nodes if node.id == previous.node_id)
            notice = FlowRenderer().render(
                source.document, ExecutionResult(previous, ending, "advanced"), user, dict(policy.capabilities)
            )
            body = notice.text + "\n\n" + screen.text
            validate_message(body)
            screen = screen.model_copy(update={"text": body})
        return await (await request.get(ScreenDeliveryService)).prepare(result, screen, update_id)

    async def _deliver(self, bot: Bot, pending: ScreenDelivery, context: TelegramFlowContext | None = None) -> None:
        async with self._container() as request:
            deliveries = await request.get(ScreenDeliveryService)
            attempt = await deliveries.claim(pending.token)
            if attempt is None:
                return
            if await (await request.get(BotStatusService)).is_stopped(attempt.chat_id):
                await deliveries.reject(attempt.token)
                return
        # Both the state and the uncertain-attempt marker are committed before any network I/O.
        try:
            if attempt.screen.feature is not None:
                if context is None:
                    raise FlowExecutionError("Feature context is unavailable")
                if attempt.screen.text:
                    await bot.send_message(attempt.chat_id, attempt.screen.text, parse_mode="HTML")
                async with self._container() as request:
                    user = await self._user(request, attempt.chat_id)
                    with i18n.context(), i18n.use_locale(user.locale), i18n.use_theme(Theme(user.theme)):
                        await open_feature(request, context, user, attempt.update_id, attempt.screen.feature)
                message_id = None
            else:
                message_id = await send_screen(bot, attempt)
        except FlowExecutionError:
            async with self._container() as request:
                await (await request.get(ScreenDeliveryService)).reject(attempt.token)
            await self._notice(bot, attempt.chat_id, buttons=False)
            return
        except TelegramAPIError as error:
            if is_permanent_recipient_error(error):
                async with self._container() as request:
                    await (await request.get(BotStatusService)).stop(attempt.chat_id)
                    await (await request.get(ScreenDeliveryService)).reject(attempt.token)
            logger.warning("UI screen delivery failed (%s, %s)", type(error).__name__, type(error.method).__name__)
            return
        async with self._container() as request:
            await (await request.get(ScreenDeliveryService)).acknowledge(attempt.token, message_id)

    async def _notice(self, bot: Bot, user_id: int, *, buttons: bool) -> None:
        async with self._container() as request:
            user = await self._user(request, user_id)
        with i18n.context(), i18n.use_locale(user.locale), i18n.use_theme(Theme(user.theme)):
            text = _("ui_flows.use_buttons") if buttons else _("ui_flows.unavailable")
        await bot.send_message(user_id, text)

    async def demo(
        self,
        bot: Bot,
        user_id: int,
        update_id: int,
        flow_id: str | None = None,
        context: TelegramFlowContext | None = None,
    ) -> None:
        try:
            pending = await self._demo(user_id, update_id, flow_id or DEMO_FLOW_ID)
        except (FlowNotFoundError, ActiveDialogError, FlowExecutionError):
            await self._notice(bot, user_id, buttons=False)
            return
        await self._deliver(bot, pending, context)

    async def install_defaults(self, author_id: int) -> None:
        async with self._container() as request:
            flows = await request.get(FlowService)
            for document in (main_menu_document(), survey_document()):
                if document.id == SURVEY_FLOW_ID and (await flows.get(MAIN_MENU_ID)).published_version is None:
                    continue
                try:
                    await flows.get(document.id)
                except FlowNotFoundError:
                    await flows.create(document)
                    await flows.publish(document.id, 0, author_id)

    async def survey(self, bot: Bot, user_id: int, update_id: int) -> None:
        await self.install_defaults(user_id)
        try:
            async with self._container() as request:
                user = await self._user(request, user_id)
                dialogs = await request.get(DialogService)
                active = await dialogs.active(user)
                if active is not None and active.flow_id == SURVEY_FLOW_ID:
                    result = await dialogs.handle(
                        NavigationEvent(
                            kind="navigation",
                            action="resume",
                            update_id=update_id,
                            user_id=user_id,
                            chat_id=user_id,
                            session_id=str(active.id),
                            expected_revision=active.revision,
                        ),
                        user,
                    )
                else:
                    if not await (await request.get(RolloutService)).allows(user_id, lock=True):
                        raise FlowExecutionError("New UI flow launches are disabled")
                    result = await dialogs.start(
                        SURVEY_FLOW_ID, user, update_id, replace_active=True, follow_returns=True
                    )
                pending = await self._prepare(request, result, user, update_id)
        except (FlowNotFoundError, FlowExecutionError):
            await self._notice(bot, user_id, buttons=False)
            return
        await self._deliver(bot, pending)

    async def menu(self, bot: Bot, user_id: int, update_id: int, navigation: Literal["study"] | None = None) -> None:
        await self.install_defaults(user_id)
        try:
            async with self._container() as request:
                user = await self._user(request, user_id)
                if not await (await request.get(RolloutService)).allows(user_id, lock=True):
                    raise FlowExecutionError("New UI flow launches are disabled")
                result = await (await request.get(DialogService)).start(
                    MAIN_MENU_ID, user, update_id, replace_active=True, navigation=navigation, follow_returns=True
                )
                pending = await self._prepare(request, result, user, update_id)
        except (FlowNotFoundError, FlowExecutionError):
            await self._notice(bot, user_id, buttons=False)
            return
        await self._deliver(bot, pending)

    async def _demo(self, user_id: int, update_id: int, flow_id: str) -> ScreenDelivery:
        async with self._container() as request:
            user = await self._user(request, user_id)
            flows = await request.get(FlowService)
            try:
                await flows.get(flow_id)
            except FlowNotFoundError:
                if flow_id != DEMO_FLOW_ID:
                    raise
                await flows.create(demo_document())
                await flows.publish(DEMO_FLOW_ID, 0, user_id)
            dialogs = await request.get(DialogService)
            active = await dialogs.active(user)
            if active is None:
                if not await (await request.get(RolloutService)).allows(user_id, lock=True):
                    raise FlowExecutionError("New UI flow launches are disabled")
                result = await dialogs.start(flow_id, user, update_id, follow_returns=True)
            else:
                if active.flow_id != flow_id:
                    raise ActiveDialogError("Finish the current pilot before opening another scenario")
                result = await dialogs.handle(
                    NavigationEvent(
                        kind="navigation",
                        action="resume",
                        update_id=update_id,
                        user_id=user_id,
                        chat_id=user_id,
                        session_id=str(active.id),
                        expected_revision=active.revision,
                    ),
                    user,
                )
            pending = await self._prepare(request, result, user, update_id)
        return pending

    async def message(
        self, bot: Bot, user_id: int, update_id: int, text: str, context: TelegramFlowContext | None = None
    ) -> None:
        try:
            async with self._container() as request:
                user = await self._user(request, user_id)
                dialogs = await request.get(DialogService)
                state = await dialogs.active(user)
                if state is None:
                    return
                button_id = await (await request.get(ScreenDeliveryService)).reply_button(state, text)
                identity = EventIdentity(
                    update_id=update_id,
                    user_id=user_id,
                    chat_id=user_id,
                    session_id=str(state.id),
                    expected_revision=state.revision,
                ).model_dump()
                event: ButtonEvent | InputEvent
                if button_id is not None:
                    event = ButtonEvent(kind="button", button_id=button_id, **identity)
                else:
                    event = InputEvent(kind="input", text=text, **identity)
                follow_returns = await (await request.get(RolloutService)).allows(user_id, lock=True)
                result = await dialogs.handle(event, user, follow_returns=follow_returns)
                pending = await self._prepare(request, result, user, update_id)
        except InvalidEventError:
            await self._notice(bot, user_id, buttons=True)
            return
        except FlowExecutionError:
            await self._notice(bot, user_id, buttons=False)
            return
        await self._deliver(bot, pending, context)

    async def callback(
        self,
        bot: Bot,
        user_id: int,
        update_id: int,
        token: str,
        index: int,
        message_id: int,
        query_id: str,
        context: TelegramFlowContext | None = None,
    ) -> None:
        try:
            async with self._container() as request:
                user = await self._user(request, user_id)
                state, button_id = await (await request.get(ScreenDeliveryService)).callback(
                    token, index, message_id, user
                )
                follow_returns = await (await request.get(RolloutService)).allows(user_id, lock=True)
                result = await (await request.get(DialogService)).handle(
                    ButtonEvent(
                        kind="button",
                        update_id=update_id,
                        user_id=user_id,
                        chat_id=user_id,
                        session_id=str(state.id),
                        expected_revision=state.revision,
                        button_id=button_id,
                    ),
                    user,
                    follow_returns=follow_returns,
                )
                pending = await self._prepare(request, result, user, update_id)
        except (StaleEventError, InvalidEventError, DialogNotFoundError, FlowExecutionError):
            with i18n.context(), i18n.use_locale(user.locale), i18n.use_theme(Theme(user.theme)):
                await self._answer(bot, query_id, _("ui_flows.expired"))
            return
        except BaseException:
            await self._answer(bot, query_id)
            raise
        await self._answer(bot, query_id)
        await self._deliver(bot, pending, context)

    @staticmethod
    async def _answer(bot: Bot, query_id: str, text: str | None = None) -> None:
        try:
            await bot.answer_callback_query(query_id, text=text, show_alert=text is not None)
        except TelegramAPIError:
            logger.warning("Could not acknowledge UI callback")

    async def leave(self, user_id: int, update_id: int) -> None:
        async with self._container() as request:
            user = await self._user(request, user_id)
            await (await request.get(DialogService)).cancel_active(user, update_id)

    async def refresh(self, bot: Bot, user_id: int, update_id: int) -> None:
        async with self._container() as request:
            user = await self._user(request, user_id)
            dialogs = await request.get(DialogService)
            state = await dialogs.active(user)
            if state is None:
                return
            result = await dialogs.handle(
                NavigationEvent(
                    kind="navigation",
                    action="resume",
                    update_id=update_id,
                    user_id=user_id,
                    chat_id=user_id,
                    session_id=str(state.id),
                    expected_revision=state.revision,
                ),
                user,
            )
            pending = await self._prepare(request, result, user, update_id)
        await self._deliver(bot, pending)
