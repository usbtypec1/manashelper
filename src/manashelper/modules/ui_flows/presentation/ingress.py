from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiogram import BaseMiddleware, Bot, Router, flags
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from aiogram.utils.i18n import gettext as _
from dishka import AsyncContainer, FromDishka
from dishka.integrations.aiogram import CONTAINER_NAME

from manashelper.core.config import Settings
from manashelper.modules.obis.presentation.router import ObisCredentialsForm
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.infrastructure.triggers import TriggerRepository
from manashelper.modules.ui_flows.menus import MAIN_MENU_ID
from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.features import TelegramFlowContext
from manashelper.modules.ui_flows.presentation.ingress_events import event_identity, normalize
from manashelper.modules.ui_flows.triggers import LEGACY_STATES
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.ingress import has_access, idle_menu, resolve
from ui_flows.domain.ingress import ExpectedPosition, IncomingEvent, IngressContext, RouteDecision
from ui_flows.domain.schema import InputNode
from ui_flows.domain.state import RuntimeUser


class IngressMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        request: AsyncContainer = data[CONTAINER_NAME]
        repository = await request.get(TriggerRepository)
        identity = event_identity(event, data["bot"], data["event_update"].update_id)
        previous = await repository.receipt(identity) if identity is not None else None
        data["ingress_replay"] = previous is not None
        if previous is not None and (
            previous.kind == "legacy" or await repository.runtime_processed(data["event_update"].update_id)
        ):
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None
        state: FSMContext | None = data.get("state")
        legacy_state = await state.get_state() if state else None
        active = None
        runtime_input = None
        if (
            isinstance(event, Message)
            and event.from_user is not None
            and (event.chat.type == "private" and event.chat.id == event.from_user.id and event.chat.id > 0)
        ):
            active = await (await request.get(DialogService)).active(RuntimeUser(event.from_user.id, event.chat.id))
            if active is not None:
                version = await (await request.get(FlowService)).version(active.flow_id, active.flow_version)
                node = next(item for item in version.document.nodes if item.id == active.node_id)
                runtime_input = node.input_type if isinstance(node, InputNode) else None
        opaque_password = isinstance(event, Message) and legacy_state == ObisCredentialsForm.password.state
        replay_text = previous is not None and previous.kind == "runtime_text"
        incoming = await normalize(
            event,
            data["bot"],
            data["event_update"].update_id,
            known_commands=frozenset() if opaque_password or replay_text else None,
        )
        if incoming is None:
            if isinstance(event, CallbackQuery):
                await event.answer(_("ui_flows.expired"), show_alert=True)
            return None
        release = None
        if opaque_password:
            release = await (await request.get(TriggerService)).current()
            settings = await request.get(Settings)
            access = IngressContext(
                settings.admin_chat_id,
                settings.moderation_chat_id,
                capabilities=frozenset({"eders_enabled"}) if settings.eders_enabled else frozenset(),
            )
            commands = frozenset(
                binding.matcher.key
                for binding in release.manifest.document.bindings
                if binding.matcher.kind == "command" and has_access(binding, incoming, access)
            )
            incoming = await normalize(event, data["bot"], data["event_update"].update_id, known_commands=commands)
            assert incoming is not None
        if previous is not None:
            if (
                previous.kind == "launch"
                and previous.policy != "call"
                and data.get("state")
                and await data["state"].get_state() is not None
            ):
                if isinstance(event, Message):
                    await event.answer(_("ui_flows.use_buttons"))
                return None
            decision = previous
        else:
            release = release or await (await request.get(TriggerService)).current()
            legacy_owner = LEGACY_STATES.get((legacy_state or "").partition(":")[0])
            saved_reply = False
            private = (
                incoming.chat_type == "private" and incoming.actor_id == incoming.chat_id and incoming.actor_id > 0
            )
            if private:
                active = await (await request.get(DialogService)).active(
                    RuntimeUser(incoming.actor_id, incoming.chat_id)
                )
                if active is not None and incoming.kind == "text":
                    saved_reply = (
                        await (await request.get(ScreenDeliveryService)).reply_button(active, incoming.text) is not None
                    )
            settings = await request.get(Settings)
            labels = {
                binding.matcher.key: i18n.reply_labels(binding.matcher.key)
                for binding in release.manifest.document.bindings
                if binding.matcher.kind == "reply_label"
            }
            context = IngressContext(
                settings.admin_chat_id,
                settings.moderation_chat_id,
                active.root_flow_id if active else None,
                legacy_owner,
                saved_reply,
                await (await request.get(RolloutService)).allows(incoming.actor_id),
                frozenset({"eders_enabled"}) if settings.eders_enabled else frozenset(),
                labels,
                active is not None and not idle_menu(active, MAIN_MENU_ID),
                runtime_input,
            )
            decision = resolve(incoming, release, context)
            if decision.kind not in {"legacy", "reject", "ignore"}:
                decision = decision.model_copy(
                    update={
                        "position": ExpectedPosition(
                            session_id=str(active.id) if active else None, revision=active.revision if active else None
                        )
                    }
                )
            if decision.kind not in {"reject", "ignore"} and not await repository.record(incoming, decision):
                # Unique receipts serialize duplicate admissions without a DB chat lock during legacy I/O.
                previous = await repository.receipt(incoming)
                if previous is None:
                    raise RuntimeError("Conflicting receipt is unavailable")
                if previous.kind == "legacy" or await repository.runtime_processed(incoming.update_id):
                    if isinstance(event, CallbackQuery):
                        await event.answer()
                    return None
                decision = previous
                data["ingress_replay"] = True
        if decision.kind in {"reject", "ignore"}:
            if decision.kind == "reject":
                if isinstance(event, CallbackQuery):
                    await event.answer(_("ui_flows.expired"), show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(_("ui_flows.use_buttons"))
            return None
        data["ingress_event"], data["ingress_route"] = incoming, decision
        data["ingress_secret"] = runtime_input == "secret" and decision.kind == "runtime_text"
        if decision.kind == "legacy" and decision.policy == "replace" and data.get("state"):
            await data["state"].clear()
        return await handler(event, data)


class LegacyRoute(Filter):
    def __init__(self, adapter: str) -> None:
        self.adapter = adapter

    async def __call__(self, event: TelegramObject, ingress_route: RouteDecision | None = None) -> bool:
        return ingress_route is None or (ingress_route.kind == "legacy" and ingress_route.adapter == self.adapter)


class RuntimeRoute(Filter):
    async def __call__(self, event: TelegramObject, ingress_route: RouteDecision | None = None) -> bool:
        return ingress_route is not None and ingress_route.kind in {"launch", "runtime_text", "runtime_callback"}


router = Router(name="ui_ingress")


@router.message(RuntimeRoute())
@flags.private_chat_only
@flags.ui_flow
@flags.mask_logged_message
async def runtime_message(
    message: Message,
    bot: Bot,
    event_update: Update,
    state: FSMContext,
    ingress_route: RouteDecision,
    ingress_event: IncomingEvent,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
    ingress_replay: bool = False,
    ingress_secret: bool = False,
) -> None:
    context = TelegramFlowContext(message, state)
    if ingress_route.kind == "launch":
        if not ingress_replay and ingress_route.policy != "call":
            await state.clear()
        after_request.add(
            lambda: coordinator.launch(
                bot, message.chat.id, event_update.update_id, ingress_route, ingress_event, context
            )
        )
    else:
        if ingress_secret:
            with suppress(TelegramAPIError):
                await message.delete()
        after_request.add(
            lambda: coordinator.message(
                bot,
                message.chat.id,
                event_update.update_id,
                message.text or "",
                context,
                ingress_route.position,
                incoming=ingress_event,
            )
        )


@router.callback_query(RuntimeRoute())
@flags.private_chat_only
@flags.ui_flow
async def runtime_callback(
    callback_query: CallbackQuery,
    bot: Bot,
    event_update: Update,
    state: FSMContext,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
    ingress_route: RouteDecision,
    ingress_event: IncomingEvent,
    ingress_replay: bool = False,
) -> None:
    message = callback_query.message
    if not isinstance(message, Message):
        return
    if ingress_route.kind == "launch":
        if not ingress_replay and ingress_route.policy != "call":
            await state.clear()
        await callback_query.answer()
        after_request.add(
            lambda: coordinator.launch(
                bot,
                callback_query.from_user.id,
                event_update.update_id,
                ingress_route,
                ingress_event,
                TelegramFlowContext(message, state),
            )
        )
        return
    parsed = UiFlowCallback.unpack(callback_query.data or "")
    after_request.add(
        lambda: coordinator.callback(
            bot,
            callback_query.from_user.id,
            event_update.update_id,
            parsed.token,
            parsed.index,
            message.message_id,
            callback_query.id,
            TelegramFlowContext(message, state),
        )
    )
