from dataclasses import asdict

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.core.config import Settings
from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.modules.broadcast.callbacks import BroadcastAction, BroadcastCallback
from manashelper.modules.broadcast.content import BroadcastButton, InvalidBroadcastButtonsError, parse_buttons
from manashelper.modules.broadcast.keyboards import (
    build_broadcast_buttons,
    build_broadcast_buttons_editor,
    build_broadcast_confirm_keyboard,
)
from manashelper.modules.broadcast.sender import TelegramBroadcastSender
from manashelper.modules.broadcast.service import BroadcastSender, SendBroadcast
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html

router = Router(name="broadcast")

_BODY_STATE_KEY = "body"
_PHOTO_STATE_KEY = "photo_id"
_BUTTONS_STATE_KEY = "buttons"


class BroadcastForm(StatesGroup):
    message = State()
    buttons = State()


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    body = data.get(_BODY_STATE_KEY, "")
    photo_id = data.get(_PHOTO_STATE_KEY)
    buttons = build_broadcast_buttons([BroadcastButton(**button) for button in data.get(_BUTTONS_STATE_KEY, [])])
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        controls = build_broadcast_confirm_keyboard()
        keyboard = buttons if buttons is not None else controls
        preview = _("broadcast.preview").format(body=escape_html(body))
        caption_fits = len(_("broadcast.preview").format(body=body).encode("utf-16-le")) // 2 <= 1024
        if photo_id:
            await message.answer_photo(
                photo=photo_id,
                caption=preview if caption_fits else None,
                reply_markup=keyboard if caption_fits else None,
            )
        if not photo_id or not caption_fits:
            await message.answer(preview, reply_markup=keyboard)
        if buttons is not None:
            await message.answer(_("broadcast.confirm_prompt"), reply_markup=controls)


def _body_fits(body: str) -> bool:
    for locale in Locale:
        preview = i18n.gettext("broadcast.preview", locale=locale.value).format(body=body)
        delivered = i18n.gettext("broadcast.admin_message", locale=locale.value).format(body=body)
        if max(len(preview.encode("utf-16-le")), len(delivered.encode("utf-16-le"))) // 2 > 4096:
            return False
    return True


async def _set_status(message: Message, text: str) -> None:
    if message.photo:
        await message.edit_caption(caption=text)
    else:
        await message.edit_text(text)


def _is_admin_chat(chat_id: int, settings: Settings) -> bool:
    """Authorization lives here, not in a service - only `Settings.admin_chat_id` may trigger a
    broadcast, the same shape as `advertisement_moderation.py::_is_moderation_chat`."""
    return chat_id == settings.admin_chat_id


@router.message(Command("broadcast"))
async def on_broadcast_command(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return

    await state.clear()
    await state.set_state(BroadcastForm.message)
    # The admin chat is a single shared destination, not a specific recipient - always rendered in
    # `DEFAULT_LOCALE`, mirroring `advertisement.py::_notify_moderation_chat`.
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await message.answer(_("broadcast.message_prompt"))


@router.message(StateFilter(BroadcastForm.message))
async def on_broadcast_message_entered(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return

    body = message.text or message.caption or ""
    photo_id = message.photo[-1].file_id if message.photo else None
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        if not body and not photo_id:
            await message.answer(_("broadcast.text_required"))
            return

        if message.media_group_id:
            await message.answer(_("broadcast.single_photo_required"))
            return
        if not _body_fits(body):
            await message.answer(_("broadcast.too_long"))
            return
        await state.update_data({_BODY_STATE_KEY: body, _PHOTO_STATE_KEY: photo_id})
        await _show_preview(message, state)


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.BUTTONS))
async def on_broadcast_buttons_requested(
    callback_query: CallbackQuery, state: FSMContext, settings: FromDishka[Settings]
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return
    if _BODY_STATE_KEY not in await state.get_data():
        await callback_query.answer()
        return
    await state.set_state(BroadcastForm.buttons)
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await callback_query.message.answer(
            _("broadcast.buttons_prompt"), reply_markup=build_broadcast_buttons_editor()
        )
    await callback_query.answer()


@router.message(StateFilter(BroadcastForm.buttons))
async def on_broadcast_buttons_entered(message: Message, state: FSMContext, settings: FromDishka[Settings]) -> None:
    if not _is_admin_chat(message.chat.id, settings):
        return
    try:
        buttons = parse_buttons(message.text or "")
    except InvalidBroadcastButtonsError:
        with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
            await message.answer(_("broadcast.invalid_buttons"), reply_markup=build_broadcast_buttons_editor())
        return
    await state.update_data({_BUTTONS_STATE_KEY: [asdict(button) for button in buttons]})
    await state.set_state(BroadcastForm.message)
    await _show_preview(message, state)


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.WITHOUT_BUTTONS))
async def on_broadcast_without_buttons(
    callback_query: CallbackQuery, state: FSMContext, settings: FromDishka[Settings]
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return
    if _BODY_STATE_KEY in await state.get_data():
        await state.update_data({_BUTTONS_STATE_KEY: []})
        await state.set_state(BroadcastForm.message)
        await _show_preview(callback_query.message, state)
    await callback_query.answer()


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.CANCEL))
async def on_broadcast_cancelled(
    callback_query: CallbackQuery, state: FSMContext, settings: FromDishka[Settings]
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return

    await state.clear()
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await _set_status(callback_query.message, _("broadcast.cancelled"))
    await callback_query.answer()


@router.callback_query(BroadcastCallback.filter(F.action == BroadcastAction.CONFIRM))
async def on_broadcast_confirmed(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    send_broadcast: FromDishka[SendBroadcast],
    locale_service: FromDishka[LocaleService],
    bot_status: FromDishka[BotStatusService],
) -> None:
    if not isinstance(callback_query.message, Message) or not _is_admin_chat(callback_query.message.chat.id, settings):
        await callback_query.answer()
        return

    data = await state.get_data()
    body = data.get(_BODY_STATE_KEY)
    photo_id = data.get(_PHOTO_STATE_KEY)
    keyboard = build_broadcast_buttons([BroadcastButton(**button) for button in data.get(_BUTTONS_STATE_KEY, [])])
    await state.clear()
    await callback_query.answer()
    if not body and not photo_id:
        return

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await _set_status(callback_query.message, _("broadcast.sending"))

    sender: BroadcastSender = TelegramBroadcastSender(
        bot, locale_service, bot_status, photo_id=photo_id, keyboard=keyboard
    )
    result = await send_broadcast.execute(body or "", sender)

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        summary_text = _("broadcast.sent").format(sent=result.sent, total=result.total)
    await bot.send_message(chat_id=callback_query.message.chat.id, text=summary_text)
