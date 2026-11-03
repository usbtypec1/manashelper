import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.i18n import gettext as _
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.localization.theme import Theme
from manashelper.modules.food_menu.ui_scenarios import food_menu_notification_scenario
from manashelper.modules.notifications.ui_scenarios import notifications_document
from manashelper.modules.schedule.ui_scenarios import schedule_scenarios
from manashelper.modules.student_questions.flow import SURVEY_FLOW_ID, survey_document
from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.demo import DEMO_FLOW_ID, demo_document
from manashelper.modules.ui_flows.infrastructure.deliveries import DeliveryRepository
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.ui_flows.infrastructure.triggers import TriggerRepository
from manashelper.modules.ui_flows.menus import MAIN_MENU_ID, main_menu_document
from manashelper.modules.ui_flows.presentation.features import TelegramFlowContext, open_feature
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, validate_message
from manashelper.modules.ui_flows.presentation.sender import send_screen
from manashelper.modules.ui_flows.triggers import orchestration_trigger_document
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.ui_scenarios import user_scenarios
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.secrets import SecretCodec
from manashelper.platform.telegram.delivery import is_permanent_recipient_error
from manashelper.platform.telegram.middlewares.per_chat_ordering import ChatOrdering
from manashelper.platform.telegram.ui_scenarios import settings_document
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.ingress import authorized, launch_arguments
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import (
    ButtonEvent,
    ContactEvent,
    EventIdentity,
    FlowEvent,
    InputEvent,
    MediaEvent,
    NavigationEvent,
    SecretEvent,
)
from ui_flows.domain.delivery import ScreenDelivery
from ui_flows.domain.ingress import ExpectedPosition, IncomingEvent, IngressContext, RouteDecision
from ui_flows.domain.schema import CallNode, EndNode, InputNode, ReplaceNode
from ui_flows.domain.state import ExecutionResult, RuntimeUser
from ui_flows.errors import (
    ActiveDialogError,
    DialogNotFoundError,
    FlowExecutionError,
    FlowNotFoundError,
    InvalidEventError,
    StaleEventError,
)
from ui_flows.ports.repositories import DialogStore

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
        request: AsyncContainer,
        result: ExecutionResult,
        user: RuntimeUser,
        update_id: int | None,
        *,
        operation_id: UUID | None = None,
    ) -> ScreenDelivery:
        # A transactional locale/theme delegate can change presentation preferences before this wait.
        user = await FlowTelegramCoordinator._user(request, user.id)
        version = await (await request.get(FlowService)).version(result.state.flow_id, result.state.flow_version)
        policy = await request.get(FlowPolicy)
        texts = await request.get(TextCatalogService)
        with i18n.use_catalog(await texts.version(version.text_catalog_release or 1)):
            screen = FlowRenderer().render(version.document, result, user, dict(policy.capabilities))
        notices = []
        for return_notice in result.notices:
            source = await (await request.get(FlowService)).version(return_notice.flow_id, return_notice.flow_version)
            node = next(item for item in source.document.nodes if item.id == return_notice.node_id)
            with i18n.use_catalog(await texts.version(source.text_catalog_release or 1)):
                rendered = FlowRenderer().render(
                    source.document, ExecutionResult(return_notice, node, "advanced"), user, dict(policy.capabilities)
                )
            if rendered.text:
                notices.append(rendered.text)
        if notices:
            if len(notices) + len(screen.messages) > 20:
                raise FlowExecutionError("Return notices exceed the screen message limit")
            screen = screen.model_copy(update={"messages": [*notices, *screen.messages]})
        if result.returned_from is not None:
            previous = result.returned_from
            source = await (await request.get(FlowService)).version(previous.flow_id, previous.flow_version)
            ending = next(node for node in source.document.nodes if node.id == previous.node_id)
            with i18n.use_catalog(await texts.version(source.text_catalog_release or 1)):
                notice = FlowRenderer().render(
                    source.document, ExecutionResult(previous, ending, "advanced"), user, dict(policy.capabilities)
                )
            body = notice.text + "\n\n" + screen.text
            validate_message(body)
            screen = screen.model_copy(update={"text": body})
        return await (await request.get(ScreenDeliveryService)).prepare(
            result, screen, update_id, operation_id=operation_id
        )

    async def _deliver(self, bot: Bot, pending: ScreenDelivery, context: TelegramFlowContext | None = None) -> None:
        async with catalog_request(self._container) as request:
            deliveries = await request.get(ScreenDeliveryService)
            attempt = await deliveries.claim(pending.token)
            if attempt is None:
                return
            if await (await request.get(BotStatusService)).is_stopped(attempt.chat_id):
                await deliveries.reject(attempt.token)
                return
            snapshot = await (await request.get(TextCatalogService)).version(attempt.screen.text_catalog_release or 1)
        # Both the state and the uncertain-attempt marker are committed before any network I/O.
        message_ids: list[int] = []
        try:
            if attempt.screen.feature is not None:
                if context is None or attempt.update_id is None:
                    raise FlowExecutionError("Feature context is unavailable")
                for text in attempt.screen.messages:
                    sent = await bot.send_message(attempt.chat_id, text, parse_mode="HTML")
                    message_ids.append(sent.message_id)
                if attempt.screen.text:
                    sent = await bot.send_message(attempt.chat_id, attempt.screen.text, parse_mode="HTML")
                    message_ids.append(sent.message_id)
                async with catalog_request(self._container) as request:
                    user = await self._user(request, attempt.chat_id)
                    with i18n.context(), i18n.use_locale(user.locale), i18n.use_theme(Theme(user.theme)):
                        await open_feature(request, context, user, attempt.update_id, attempt.screen.feature)
                message_id = None
            else:
                with i18n.use_catalog(snapshot):
                    message_id = await send_screen(bot, attempt, delivered=message_ids)
        except BaseException as error:
            # Keep known IDs even when cancellation or an unexpected failure interrupts a rich screen.
            # The claim remains unknown: recording partial progress must never cause an automatic resend.
            if message_ids:
                async with catalog_request(self._container) as request:
                    await (await request.get(ScreenDeliveryService)).partial(attempt.token, tuple(message_ids))
            if isinstance(error, FlowExecutionError):
                async with catalog_request(self._container) as request:
                    await (await request.get(ScreenDeliveryService)).reject(attempt.token)
                await self._notice(bot, attempt.chat_id, buttons=False)
                return
            if isinstance(error, TelegramAPIError):
                if is_permanent_recipient_error(error):
                    async with catalog_request(self._container) as request:
                        await (await request.get(BotStatusService)).stop(attempt.chat_id)
                        await (await request.get(ScreenDeliveryService)).reject(attempt.token)
                logger.warning("UI screen delivery failed (%s, %s)", type(error).__name__, type(error.method).__name__)
                return
            raise
        async with catalog_request(self._container) as request:
            await (await request.get(ScreenDeliveryService)).acknowledge(
                attempt.token, message_id, message_ids=tuple(message_ids)
            )
        (await self._container.get(EffectWorker)).notify()

    async def complete_effect(self, bot: Bot, operation_id: UUID) -> None:
        # Resolve the scope before waiting for the shared gate; never keep a REQUEST open in its queue.
        async with self._container() as request:
            operation = await (await request.get(EffectRepository)).get(operation_id)
            if operation is None:
                return
        ordering = await self._container.get(ChatOrdering)
        async with ordering.lock(operation.chat_id):
            async with catalog_request(self._container) as request:
                pending = await (await request.get(DeliveryRepository)).by_operation(operation_id)
                if pending is None:
                    user = await self._user(request, operation.user_id)
                    result = await (await request.get(DialogService)).apply_effect(operation_id, user)
                    if result is None:
                        return
                    pending = await self._prepare(request, result, user, None, operation_id=operation_id)
            await self._deliver(bot, pending)

    async def _notice(self, bot: Bot, user_id: int, *, buttons: bool) -> None:
        async with catalog_request(self._container) as request:
            user = await self._user(request, user_id)
            snapshot = i18n.current_catalog
        with (
            i18n.context(),
            i18n.use_catalog(snapshot),
            i18n.use_locale(user.locale),
            i18n.use_theme(Theme(user.theme)),
        ):
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
        async with catalog_request(self._container) as request:
            flows = await request.get(FlowService)
            for document in (
                *user_scenarios(),
                *schedule_scenarios(),
                food_menu_notification_scenario(),
                notifications_document(),
                settings_document(),
                main_menu_document(),
                survey_document(),
            ):
                try:
                    await flows.get(document.id)
                except FlowNotFoundError:
                    dependencies = {
                        node.flow if isinstance(node, (CallNode, ReplaceNode)) else node.return_flow
                        for node in document.nodes
                        if isinstance(node, (CallNode, ReplaceNode))
                        or (isinstance(node, EndNode) and node.return_flow is not None)
                    }
                    ready = True
                    for dependency in dependencies:
                        if dependency is None or dependency == document.id:
                            continue
                        try:
                            ready &= (await flows.get(dependency)).published_version is not None
                        except FlowNotFoundError:
                            ready = False
                    if not ready:
                        continue
                    await flows.create(document)
                    await flows.publish(document.id, 0, author_id)
            await (await request.get(TriggerService)).initialize(author_id, orchestration_trigger_document())

    async def launch(
        self,
        bot: Bot,
        user_id: int,
        update_id: int,
        route: RouteDecision,
        incoming: IncomingEvent,
        context: TelegramFlowContext | None = None,
    ) -> None:
        if route.flow_id is None:
            raise FlowExecutionError("Scenario target is required")
        try:
            async with catalog_request(self._container) as request:
                user = await self._user(request, user_id)
                dialogs = await request.get(DialogService)
                active = await dialogs.active(user)
                release = await (await request.get(TriggerRepository)).version(route.release_id)
                binding = next(item for item in release.manifest.document.bindings if item.id == route.binding_id)
                settings = await request.get(Settings)
                admission = IngressContext(
                    settings.admin_chat_id,
                    settings.moderation_chat_id,
                    capabilities=frozenset({"eders_enabled"}) if settings.eders_enabled else frozenset(),
                )
                if not authorized(binding, incoming, admission) or (
                    incoming.actor_id,
                    incoming.chat_id,
                    incoming.bot_id,
                    incoming.update_id,
                ) != (user.id, user.chat_id, bot.id, update_id):
                    raise FlowExecutionError("Launch permission has changed")
                if route.position is not None and not route.position.matches(active):
                    raise FlowExecutionError("The admitted chat position has changed")
                arguments = launch_arguments(binding, incoming)
                if route.policy == "call" and (active is None or active.flow_id != route.flow_id):
                    if active is None and not await (await request.get(RolloutService)).allows(user_id, lock=True):
                        raise FlowExecutionError("New UI flow launches are disabled")
                    result = await dialogs.interrupt(
                        route.flow_id,
                        user,
                        update_id,
                        trigger_release=route.release_id,
                        arguments=arguments,
                        position=route.position,
                    )
                elif (
                    route.policy in {"resume", "call"}
                    and active is not None
                    and (active.root_flow_id == route.flow_id or active.flow_id == route.flow_id)
                ):
                    result = await dialogs.handle(
                        NavigationEvent(
                            kind="navigation",
                            action="resume",
                            update_id=update_id,
                            user_id=user.id,
                            chat_id=user.chat_id,
                            session_id=str(active.id),
                            expected_revision=active.revision,
                        ),
                        user,
                    )
                else:
                    if not await (await request.get(RolloutService)).allows(user_id, lock=True):
                        raise FlowExecutionError("New UI flow launches are disabled")
                    result = await dialogs.start(
                        route.flow_id,
                        user,
                        update_id,
                        replace_active=route.policy == "replace",
                        follow_returns=True,
                        trigger_release=route.release_id,
                        entry=route.entry,
                        navigation=route.navigation,
                        replace_idle_menu=MAIN_MENU_ID,
                        position=route.position,
                        arguments=arguments,
                    )
                pending = await self._prepare(request, result, user, update_id)
        except (FlowNotFoundError, ActiveDialogError, FlowExecutionError, StaleEventError):
            await self._notice(bot, user_id, buttons=False)
            return
        await self._deliver(bot, pending, context)

    async def survey(self, bot: Bot, user_id: int, update_id: int) -> None:
        await self.install_defaults(user_id)
        try:
            async with catalog_request(self._container) as request:
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
            async with catalog_request(self._container) as request:
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
        async with catalog_request(self._container) as request:
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
                if active.root_flow_id != flow_id:
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
        self,
        bot: Bot,
        user_id: int,
        update_id: int,
        text: str,
        context: TelegramFlowContext | None = None,
        position: ExpectedPosition | None = None,
        *,
        incoming: IncomingEvent | None = None,
    ) -> None:
        try:
            async with catalog_request(self._container) as request:
                user = await self._user(request, user_id)
                dialogs = await request.get(DialogService)
                await (await request.get(DialogStore)).lock_chat(user.chat_id)
                state = await dialogs.active(user)
                if state is None:
                    return
                if position is not None and not position.matches(state):
                    raise InvalidEventError("The admitted input position has changed")
                button_id = await (await request.get(ScreenDeliveryService)).reply_button(state, text)
                identity = EventIdentity(
                    update_id=update_id,
                    user_id=user_id,
                    chat_id=user_id,
                    session_id=str(state.id),
                    expected_revision=state.revision,
                ).model_dump()
                version = await (await request.get(FlowService)).version(state.flow_id, state.flow_version)
                node = next(item for item in version.document.nodes if item.id == state.node_id)
                event: FlowEvent
                if button_id is not None:
                    event = ButtonEvent(kind="button", button_id=button_id.id, snapshot=button_id.snapshot, **identity)
                elif isinstance(node, InputNode) and node.input_type == "secret":
                    if not node.min_length <= len(text.strip()) <= node.max_length:
                        raise InvalidEventError("Secret input length is invalid")
                    handle = uuid4()
                    codec = await request.get(SecretCodec)
                    encrypted = codec.encrypt(text.strip(), handle, state.id, user.id, user.chat_id)
                    await (await request.get(EffectRepository)).put_secret(
                        handle, state.id, user.id, user.chat_id, encrypted, datetime.now(UTC) + timedelta(minutes=5)
                    )
                    event = SecretEvent(kind="secret", handle=str(handle), **identity)
                elif incoming is not None and incoming.kind == "contact":
                    event = ContactEvent(
                        kind="contact", phone=incoming.phone or "", owner_id=incoming.contact_owner, **identity
                    )
                elif (
                    incoming is not None
                    and incoming.kind == "media"
                    and incoming.file_ids
                    and incoming.media_type in {"photo", "video"}
                ):
                    event = MediaEvent(
                        kind="media",
                        message_id=incoming.message_id or update_id,
                        file_id=incoming.file_ids[0],
                        media_type="photo" if incoming.media_type == "photo" else "video",
                        media_group_id=incoming.media_group_id,
                        caption=incoming.caption,
                        **identity,
                    )
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
            async with catalog_request(self._container) as request:
                snapshot = i18n.current_catalog
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
                        button_id=button_id.id,
                        snapshot=button_id.snapshot,
                    ),
                    user,
                    follow_returns=follow_returns,
                )
                pending = await self._prepare(request, result, user, update_id)
        except (StaleEventError, InvalidEventError, DialogNotFoundError, FlowExecutionError):
            with (
                i18n.context(),
                i18n.use_catalog(snapshot),
                i18n.use_locale(user.locale),
                i18n.use_theme(Theme(user.theme)),
            ):
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
        async with catalog_request(self._container) as request:
            user = await self._user(request, user_id)
            await (await request.get(DialogService)).cancel_active(user, update_id)

    async def refresh(self, bot: Bot, user_id: int, update_id: int) -> None:
        async with catalog_request(self._container) as request:
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
