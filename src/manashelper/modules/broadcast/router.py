from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.config import Settings
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.modules.broadcast.callbacks import BroadcastAction, BroadcastCallback
from manashelper.modules.broadcast.keyboards import build_broadcast_confirm_keyboard
from manashelper.modules.broadcast.sender import TelegramBroadcastSender
from manashelper.modules.broadcast.service import BroadcastSender, SendBroadcast
from manashelper.services.html_sanitization import escape_html
from manashelper.services.locale import LocaleService

router = Router(name="broadcast")

_BODY_STATE_KEY = "body"


class BroadcastForm(StatesGroup):
    message = State()


def _is_admin_chat(chat_id: int, settings: Settings) -> bool:
    """Authorization lives here, not in a service - only `Settings.admin_chat_id` may trigger a
    broadcast, the same shape as `advertisement_moderation.py::_is_moderation_chat`."""
    return chat_id == settings.admin_chat_id


@router.message(Command("broadcast"))
async def on_broadcast_command(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return

    await state.set_state(BroadcastForm.message)
    # The admin chat is a single shared destination, not a specific recipient - always rendered in
    # `DEFAULT_LOCALE`, mirroring `advertisement.py::_notify_moderation_chat`.
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await message.answer(_("broadcast.message_prompt"))


@router.message(StateFilter(BroadcastForm.message))
async def on_broadcast_message_entered(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return

    body = message.text or message.caption
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        if not body:
            await message.answer(_("broadcast.text_required"))
            return

        await state.update_data({_BODY_STATE_KEY: body})
        preview = _("broadcast.preview").format(body=escape_html(body))
        await message.answer(preview, reply_markup=build_broadcast_confirm_keyboard())


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.CANCEL))
async def on_broadcast_cancelled(
    callback_query: CallbackQuery, state: FSMContext, settings: FromDishka[Settings]
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return

    await state.clear()
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await callback_query.message.edit_text(_("broadcast.cancelled"))
    await callback_query.answer()


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.CONFIRM))
async def on_broadcast_confirmed(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    send_broadcast: FromDishka[SendBroadcast],
    locale_service: FromDishka[LocaleService],
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return

    data = await state.get_data()
    body = data.get(_BODY_STATE_KEY)
    await state.clear()
    await callback_query.answer()
    if not body:
        return

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await callback_query.message.edit_text(_("broadcast.sending"))

    sender: BroadcastSender = TelegramBroadcastSender(bot, locale_service)
    result = await send_broadcast.execute(body, sender)

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        summary_text = _("broadcast.sent").format(sent=result.sent, total=result.total)
    await bot.send_message(chat_id=callback_query.message.chat.id, text=summary_text)
