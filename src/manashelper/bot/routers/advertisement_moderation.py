import logging
import uuid

from aiogram import Bot, F, Router, flags
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import AdvertisementModerationAction, AdvertisementModerationCallback
from manashelper.bot.keyboards.advertisement_moderation import build_reject_comment_choice_keyboard
from manashelper.config import Settings
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.services.advertisement import AdvertisementNotFoundError, AdvertisementService, AdvertisementSummary
from manashelper.services.advertisement_formatter import build_media_group, format_advertisement
from manashelper.services.advertisement_moderation import (
    AdvertisementModerationService,
    AdvertisementNotPendingError,
    ModeratorForbiddenError,
)
from manashelper.services.locale import LocaleService
from manashelper.services.user_contact import UserContactService, UserNotFoundError

logger = logging.getLogger(__name__)

router = Router(name="advertisement_moderation")


class AdvertisementModerationForm(StatesGroup):
    comment = State()


async def _notify_owner(bot: Bot, locale_service: LocaleService, owner_id: int, text: str) -> None:
    locale = await locale_service.get_locale(owner_id)
    with i18n.context(), i18n.use_locale(locale.value):
        message = text
    try:
        await bot.send_message(chat_id=owner_id, text=message)
    except TelegramAPIError:
        logger.warning("Failed to notify advertisement owner %s", owner_id, exc_info=True)


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.APPROVE))
@flags.private_chat_only
async def on_approve(
    callback_query: CallbackQuery,
    callback_data: AdvertisementModerationCallback,
    bot: Bot,
    settings: FromDishka[Settings],
    advertisement_service: FromDishka[AdvertisementService],
    moderation_service: FromDishka[AdvertisementModerationService],
    user_contact_service: FromDishka[UserContactService],
    locale_service: FromDishka[LocaleService],
) -> None:
    try:
        summary = await moderation_service.approve(callback_data.id, callback_query.from_user.id)
    except ModeratorForbiddenError:
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return
    except AdvertisementNotFoundError:
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return
    except AdvertisementNotPendingError:
        await callback_query.answer(_("This ad has already been reviewed"), show_alert=True)
        return

    try:
        contact = await user_contact_service.get_contact_status(summary.user_id)
    except UserNotFoundError:
        contact = None

    # The channel is a single shared, public place - its posts always render in `DEFAULT_LOCALE`,
    # regardless of which moderator's own locale approved the ad (unlike every other message this
    # handler sends, which is scoped to a specific recipient's locale).
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        caption = format_advertisement(summary, contact=contact)
    try:
        if summary.media:
            sent_media = await bot.send_media_group(
                chat_id=settings.advertisement_channel_id, media=build_media_group(caption, summary.media)
            )
            message_ids = [sent.message_id for sent in sent_media]
        else:
            sent_message = await bot.send_message(chat_id=settings.advertisement_channel_id, text=caption)
            message_ids = [sent_message.message_id]
    except TelegramAPIError:
        logger.exception("Failed to publish advertisement %s to the channel", callback_data.id)
        await callback_query.answer(_("Failed to publish this ad. Please try again later."), show_alert=True)
        return

    await advertisement_service.record_channel_messages(callback_data.id, message_ids)

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Approved and published ✅"))
    await callback_query.answer()

    await _notify_owner(
        bot,
        locale_service,
        summary.user_id,
        _('Your ad "{title}" has been approved and published! 🎉').format(title=summary.title),
    )


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.REJECT))
@flags.private_chat_only
async def on_reject_requested(callback_query: CallbackQuery, callback_data: AdvertisementModerationCallback) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("Reject this ad. Would you like to add a comment explaining why?"),
            reply_markup=build_reject_comment_choice_keyboard(callback_data.id),
        )
    await callback_query.answer()


def _owner_rejection_text(summary: AdvertisementSummary, comment: str | None) -> str:
    text = _('Your ad "{title}" was not approved.').format(title=summary.title)
    if comment:
        text += "\n" + _("Reason: {comment}").format(comment=comment)
    return text


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.SKIP_COMMENT))
@flags.private_chat_only
async def on_reject_without_comment(
    callback_query: CallbackQuery,
    callback_data: AdvertisementModerationCallback,
    bot: Bot,
    moderation_service: FromDishka[AdvertisementModerationService],
    locale_service: FromDishka[LocaleService],
) -> None:
    try:
        summary = await moderation_service.reject(callback_data.id, callback_query.from_user.id, None)
    except ModeratorForbiddenError:
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return
    except AdvertisementNotFoundError:
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return
    except AdvertisementNotPendingError:
        await callback_query.answer(_("This ad has already been reviewed"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Rejected ❌"))
    await callback_query.answer()

    await _notify_owner(bot, locale_service, summary.user_id, _owner_rejection_text(summary, None))


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.ADD_COMMENT))
@flags.private_chat_only
async def on_reject_add_comment_requested(
    callback_query: CallbackQuery, callback_data: AdvertisementModerationCallback, state: FSMContext
) -> None:
    if not isinstance(callback_query.message, Message):
        await callback_query.answer()
        return

    await state.set_state(AdvertisementModerationForm.comment)
    await state.update_data(
        advertisement_id=str(callback_data.id),
        notification_chat_id=callback_query.message.chat.id,
        notification_message_id=callback_query.message.message_id,
    )
    await callback_query.message.edit_text(_("Please send the rejection comment as a text message:"))
    await callback_query.answer()


@router.message(StateFilter(AdvertisementModerationForm.comment))
@flags.private_chat_only
async def on_reject_comment_entered(
    message: Message,
    state: FSMContext,
    bot: Bot,
    moderation_service: FromDishka[AdvertisementModerationService],
    locale_service: FromDishka[LocaleService],
) -> None:
    comment = message.text.strip() if message.text else ""
    if not comment:
        await message.answer(_("The comment can't be empty. Please try again:"))
        return

    data = await state.get_data()
    advertisement_id_raw = data.get("advertisement_id")
    notification_chat_id = data.get("notification_chat_id")
    notification_message_id = data.get("notification_message_id")
    await state.clear()

    if (
        message.from_user is None
        or not advertisement_id_raw
        or notification_chat_id is None
        or notification_message_id is None
    ):
        await message.answer(_("Something went wrong. Please try again."))
        return
    advertisement_id = uuid.UUID(advertisement_id_raw)

    try:
        summary = await moderation_service.reject(advertisement_id, message.from_user.id, comment[:512])
    except ModeratorForbiddenError:
        await message.answer(_("You don't have permission to do this"))
        return
    except AdvertisementNotFoundError:
        await message.answer(_("This ad no longer exists"))
        return
    except AdvertisementNotPendingError:
        await message.answer(_("This ad has already been reviewed"))
        return

    try:
        await bot.edit_message_text(
            chat_id=notification_chat_id, message_id=notification_message_id, text=_("Rejected ❌")
        )
    except TelegramAPIError:
        logger.warning("Failed to edit moderation message for advertisement %s", advertisement_id, exc_info=True)

    await message.answer(_("Rejection sent ✅"))
    await _notify_owner(bot, locale_service, summary.user_id, _owner_rejection_text(summary, comment))
