from aiogram import Bot, F, Router, flags
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Update
from aiogram.utils.i18n import gettext as _
from dishka import AsyncContainer, FromDishka

from manashelper.core.config import get_settings
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.features import TelegramFlowContext
from manashelper.platform.telegram.middlewares.after_request import AfterRequestActions
from manashelper.platform.web.login import AdminLoginCoordinator
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser

router = Router(name="ui_flows")
reply_router = Router(name="ui_flow_reply")


class AdminFlowChat(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == ChatType.PRIVATE and message.chat.id == get_settings().admin_chat_id


def private_user(message: Message) -> bool:
    return (
        message.from_user is not None
        and message.chat.type == ChatType.PRIVATE
        and message.chat.id == message.from_user.id
        and message.chat.id > 0
    )


class FlowLaunchChat(Filter):
    async def __call__(self, message: Message, dishka_container: AsyncContainer) -> bool:
        return private_user(message) and await (await dishka_container.get(RolloutService)).allows(message.chat.id)


class ActiveFlow(Filter):
    async def __call__(self, message: Message, dishka_container: AsyncContainer) -> bool:
        if not private_user(message) or message.from_user is None or (message.text or "").startswith("/"):
            return False
        dialogs = await dishka_container.get(DialogService)
        return await dialogs.active(RuntimeUser(message.from_user.id, message.chat.id)) is not None


class ActiveReplyButton(Filter):
    async def __call__(self, message: Message, dishka_container: AsyncContainer) -> bool:
        if not private_user(message) or message.from_user is None or (message.text or "").startswith("/"):
            return False
        state = await (await dishka_container.get(DialogService)).active(
            RuntimeUser(message.from_user.id, message.chat.id)
        )
        return (
            state is not None
            and await (await dishka_container.get(ScreenDeliveryService)).reply_button(state, message.text or "")
            is not None
        )


@router.message(AdminFlowChat(), Command("editor"))
@flags.private_chat_only
@flags.preserve_ui_flow
async def on_editor(
    message: Message, bot: Bot, after_request: AfterRequestActions, login: FromDishka[AdminLoginCoordinator]
) -> None:
    after_request.add(lambda: login.open(bot, message.chat.id))


@router.message(AdminFlowChat(), Command("flow_demo"))
@flags.private_chat_only
@flags.ui_flow
async def on_flow_demo(
    message: Message,
    bot: Bot,
    event_update: Update,
    state: FSMContext,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
    command: CommandObject,
) -> None:
    await state.clear()
    after_request.add(
        lambda: coordinator.demo(
            bot, message.chat.id, event_update.update_id, command.args, TelegramFlowContext(message, state)
        )
    )


@router.message(ActiveFlow())
@flags.private_chat_only
@flags.ui_flow
@flags.mask_logged_message
async def on_flow_message(
    message: Message,
    bot: Bot,
    event_update: Update,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
    state: FSMContext,
) -> None:
    after_request.add(
        lambda: coordinator.message(
            bot, message.chat.id, event_update.update_id, message.text or "", TelegramFlowContext(message, state)
        )
    )


@router.callback_query(UiFlowCallback.filter())
@flags.private_chat_only
@flags.ui_flow
async def on_flow_callback(
    callback_query: CallbackQuery,
    bot: Bot,
    callback_data: UiFlowCallback,
    event_update: Update,
    after_request: AfterRequestActions,
    coordinator: FromDishka[FlowTelegramCoordinator],
    state: FSMContext,
) -> None:
    message = callback_query.message
    if (
        not isinstance(message, Message)
        or message.chat.type != ChatType.PRIVATE
        or message.chat.id != callback_query.from_user.id
    ):
        await callback_query.answer(_("ui_flows.expired"), show_alert=True)
        return
    after_request.add(
        lambda: coordinator.callback(
            bot,
            callback_query.from_user.id,
            event_update.update_id,
            callback_data.token,
            callback_data.index,
            message.message_id,
            callback_query.id,
            TelegramFlowContext(message, state),
        )
    )


reply_router.message.register(
    on_flow_message,
    ActiveReplyButton(),
    flags={"private_chat_only": True, "ui_flow": True, "mask_logged_message": True},
)


@router.callback_query(F.data.startswith("uf:"))
@flags.private_chat_only
@flags.ui_flow
async def on_invalid_flow_callback(callback_query: CallbackQuery) -> None:
    await callback_query.answer(_("ui_flows.expired"), show_alert=True)
