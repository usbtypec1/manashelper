import logging
import uuid
from collections.abc import Callable

from aiogram import Bot, F, Router
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
from manashelper.services.advertisement_moderation import AdvertisementModerationService, AdvertisementNotPendingError
from manashelper.services.html_sanitization import escape_html
from manashelper.services.locale import LocaleService

logger = logging.getLogger(__name__)

router = Router(name="advertisement_moderation")

AD_DEEPLINK_PAYLOAD_PREFIX = "ad_"


class AdvertisementModerationForm(StatesGroup):
    comment = State()


def _is_moderation_chat(callback_query: CallbackQuery, settings: Settings) -> bool:
    """Authorization for every moderation action lives here, not in the service layer: only a
    callback originating from the configured moderation chat is accepted - there is no per-user
    moderator role. This also guards against a forwarded copy of the review message (Telegram
    preserves inline keyboards across forwards) being actioned from some other chat."""
    return isinstance(callback_query.message, Message) and callback_query.message.chat.id == settings.moderation_chat_id


async def _notify_owner(bot: Bot, locale_service: LocaleService, owner_id: int, build_text: Callable[[], str]) -> None:
    """`build_text` is called *inside* the owner's own locale context, not the caller's - a plain
    pre-built string would be resolved under whichever moderator's locale triggered the action."""
    locale = await locale_service.get_locale(owner_id)
    with i18n.context(), i18n.use_locale(locale.value):
        message = build_text()
    try:
        await bot.send_message(chat_id=owner_id, text=message)
    except TelegramAPIError:
        logger.warning("Failed to notify advertisement owner %s", owner_id, exc_info=True)


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.APPROVE))
async def on_approve(
    callback_query: CallbackQuery,
    callback_data: AdvertisementModerationCallback,
    bot: Bot,
    settings: FromDishka[Settings],
    advertisement_service: FromDishka[AdvertisementService],
    moderation_service: FromDishka[AdvertisementModerationService],
    locale_service: FromDishka[LocaleService],
) -> None:
    if not _is_moderation_chat(callback_query, settings):
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return

    try:
        summary = await moderation_service.approve(callback_data.id)
    except AdvertisementNotFoundError:
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return
    except AdvertisementNotPendingError:
        await callback_query.answer(_("This ad has already been reviewed"), show_alert=True)
        return

    # Contacts aren't shown directly on the (public) channel post - only via this deep link, which
    # routes through `on_advertisement_deep_link` and gets logged in `AdvertisementContactView`.
    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start={AD_DEEPLINK_PAYLOAD_PREFIX}{summary.id}"

    # The channel is a single shared, public place - its posts always render in `DEFAULT_LOCALE`,
    # regardless of which moderator's own locale approved the ad (unlike every other message this
    # handler sends, which is scoped to a specific recipient's locale).
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        caption = format_advertisement(summary, contact_deep_link=deep_link)
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
        lambda: _('Your ad "{title}" has been approved and published! 🎉').format(title=escape_html(summary.title)),
    )


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.REJECT))
async def on_reject_requested(
    callback_query: CallbackQuery, callback_data: AdvertisementModerationCallback, settings: FromDishka[Settings]
) -> None:
    if not _is_moderation_chat(callback_query, settings):
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("Reject this ad. Would you like to add a comment explaining why?"),
            reply_markup=build_reject_comment_choice_keyboard(callback_data.id),
        )
    await callback_query.answer()


def _build_owner_rejection_text(summary: AdvertisementSummary, comment: str | None) -> str:
    text = _('Your ad "{title}" was not approved.').format(title=escape_html(summary.title))
    if comment:
        text += "\n" + _("Reason: {comment}").format(comment=escape_html(comment))
    return text


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.SKIP_COMMENT))
async def on_reject_without_comment(
    callback_query: CallbackQuery,
    callback_data: AdvertisementModerationCallback,
    bot: Bot,
    settings: FromDishka[Settings],
    moderation_service: FromDishka[AdvertisementModerationService],
    locale_service: FromDishka[LocaleService],
) -> None:
    if not _is_moderation_chat(callback_query, settings):
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return

    try:
        summary = await moderation_service.reject(callback_data.id, None)
    except AdvertisementNotFoundError:
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return
    except AdvertisementNotPendingError:
        await callback_query.answer(_("This ad has already been reviewed"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Rejected ❌"))
    await callback_query.answer()

    await _notify_owner(bot, locale_service, summary.user_id, lambda: _build_owner_rejection_text(summary, None))


@router.callback_query(AdvertisementModerationCallback.filter(F.action == AdvertisementModerationAction.ADD_COMMENT))
async def on_reject_add_comment_requested(
    callback_query: CallbackQuery,
    callback_data: AdvertisementModerationCallback,
    settings: FromDishka[Settings],
    state: FSMContext,
) -> None:
    if not _is_moderation_chat(callback_query, settings):
        await callback_query.answer(_("You don't have permission to do this"), show_alert=True)
        return
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

    if not advertisement_id_raw or notification_chat_id is None or notification_message_id is None:
        await message.answer(_("Something went wrong. Please try again."))
        return
    advertisement_id = uuid.UUID(advertisement_id_raw)

    try:
        summary = await moderation_service.reject(advertisement_id, comment[:512])
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
    await _notify_owner(bot, locale_service, summary.user_id, lambda: _build_owner_rejection_text(summary, comment))
