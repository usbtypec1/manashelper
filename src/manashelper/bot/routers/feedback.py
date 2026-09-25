import logging

from aiogram import Bot, F, Router, flags
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import FeedbackAction, FeedbackCallback, SettingsAction, SettingsCallback
from manashelper.bot.keyboards.feedback import build_feedback_cancel_keyboard
from manashelper.bot.keyboards.settings import build_settings_keyboard
from manashelper.config import Settings
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.services.feedback import BODY_MAX_LENGTH, FeedbackService
from manashelper.services.html_sanitization import escape_html
from manashelper.services.locale import LocaleService

logger = logging.getLogger(__name__)

router = Router(name="feedback")


class FeedbackForm(StatesGroup):
    message = State()


def _is_admin_chat(message: Message, settings: Settings) -> bool:
    return message.chat.id == settings.admin_chat_id


@router.callback_query(SettingsCallback.filter(F.action == SettingsAction.OPEN_FEEDBACK))
@flags.private_chat_only
async def on_open_feedback(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FeedbackForm.message)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _(
                "💬 Please type the message you'd like to send to the administration. We'll reply "
                "here as soon as possible."
            ),
            reply_markup=build_feedback_cancel_keyboard(),
        )
    await callback_query.answer()


@router.callback_query(FeedbackCallback.filter(F.action == FeedbackAction.CANCEL))
@flags.private_chat_only
async def on_feedback_cancelled(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Settings"), reply_markup=build_settings_keyboard())
    await callback_query.answer()


@router.message(StateFilter(FeedbackForm.message))
@flags.private_chat_only
async def on_feedback_entered(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    feedback_service: FromDishka[FeedbackService],
) -> None:
    body = message.text.strip() if message.text else ""
    if not body or len(body) > BODY_MAX_LENGTH:
        await message.answer(
            _("The message can't be empty and must be at most {max} characters long. Please try again:").format(
                max=BODY_MAX_LENGTH
            ),
            reply_markup=build_feedback_cancel_keyboard(),
        )
        return
    if message.from_user is None:
        return

    await state.clear()
    summary = await feedback_service.submit(message.from_user.id, body)
    await message.answer(_("✅ Thank you! Your message has been sent to the administration."))

    sender = f"@{message.from_user.username}" if message.from_user.username else str(message.from_user.id)
    # A single shared destination, not a specific recipient's chat - always rendered in
    # `DEFAULT_LOCALE`, mirroring `advertisement.py::_notify_moderation_chat`.
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        text = _("💬 <b>New feedback</b> from {sender}:\n\n{body}\n\n<i>Reply to this message to answer.</i>").format(
            sender=escape_html(sender), body=escape_html(body)
        )
    try:
        sent = await bot.send_message(chat_id=settings.admin_chat_id, text=text)
    except TelegramAPIError:
        logger.warning("Failed to forward feedback message %s to the admin chat", summary.id, exc_info=True)
        return

    await feedback_service.record_admin_chat_message(summary.id, sent.message_id)


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.reply_to_message)
async def on_admin_reply(
    message: Message,
    bot: Bot,
    settings: FromDishka[Settings],
    feedback_service: FromDishka[FeedbackService],
    locale_service: FromDishka[LocaleService],
) -> None:
    if not _is_admin_chat(message, settings) or message.reply_to_message is None:
        return

    feedback = await feedback_service.get_by_admin_chat_message_id(message.reply_to_message.message_id)
    if feedback is None:
        return

    reply_text = message.text or message.caption
    if not reply_text:
        return

    locale = await locale_service.get_locale(feedback.user_id)
    with i18n.context(), i18n.use_locale(locale.value):
        text = _("📩 <b>Reply from the administration:</b>\n\n{text}").format(text=escape_html(reply_text))

    try:
        await bot.send_message(chat_id=feedback.user_id, text=text)
    except TelegramAPIError:
        logger.warning("Failed to relay admin reply to user %s", feedback.user_id, exc_info=True)
        with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
            await message.reply(_("⚠️ Failed to deliver the reply to the user."))
        return

    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        await message.reply(_("Reply sent ✅"))
