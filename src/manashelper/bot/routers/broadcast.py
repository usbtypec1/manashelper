import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import BroadcastAction, BroadcastCallback
from manashelper.bot.keyboards.broadcast import build_broadcast_confirm_keyboard
from manashelper.config import Settings
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.services.broadcast import BroadcastService
from manashelper.services.html_sanitization import escape_html
from manashelper.services.locale import LocaleService

logger = logging.getLogger(__name__)

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
        await message.answer(_("📢 Send the message you want to broadcast to every user:"))


@router.message(StateFilter(BroadcastForm.message))
async def on_broadcast_message_entered(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return

    body = message.text or message.caption
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        if not body:
            await message.answer(_("Please send the broadcast as a text message."))
            return

        await state.update_data({_BODY_STATE_KEY: body})
        preview = _("📢 <b>Broadcast preview:</b>\n\n{body}\n\nSend this to every user?").format(body=escape_html(body))
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
        await callback_query.message.edit_text(_("❌ Broadcast cancelled."))
    await callback_query.answer()


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.CONFIRM))
async def on_broadcast_confirmed(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    broadcast_service: FromDishka[BroadcastService],
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
        await callback_query.message.edit_text(_("📤 Sending broadcast…"))

    recipient_ids = await broadcast_service.get_recipient_ids()
    sent_count = 0
    for user_id in recipient_ids:
        locale = await locale_service.get_locale(user_id)
        with i18n.context(), i18n.use_locale(locale.value):
            text = _("📢 <b>Message from the administration</b>\n\n{body}").format(body=escape_html(body))
        try:
            await bot.send_message(chat_id=user_id, text=text)
            sent_count += 1
        except TelegramAPIError:
            logger.warning("Failed to deliver broadcast to user %s", user_id, exc_info=True)

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        summary_text = _("✅ Broadcast sent to {sent}/{total} users.").format(sent=sent_count, total=len(recipient_ids))
    await bot.send_message(chat_id=callback_query.message.chat.id, text=summary_text)
