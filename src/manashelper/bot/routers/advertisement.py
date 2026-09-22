import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot, F, Router, flags
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    AdvertisementCallback,
    AdvertisementDeleteAction,
    AdvertisementDeleteCallback,
    AdvertisementExpiryCallback,
    AdvertisementExpiryOption,
    AdvertisementFormAction,
    AdvertisementFormCallback,
    AdvertisementsPageCallback,
)
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.advertisement import (
    build_advertisement_delete_confirm_keyboard,
    build_advertisement_detail_keyboard,
    build_advertisement_menu_keyboard,
    build_cancel_form_keyboard,
    build_confirm_keyboard,
    build_expiry_keyboard,
    build_media_keyboard,
    build_my_ads_keyboard,
    build_skip_price_keyboard,
)
from manashelper.bot.keyboards.advertisement_moderation import build_moderation_keyboard
from manashelper.bot.keyboards.phone_numbers import build_contact_request_keyboard
from manashelper.bot.routers.start import build_main_keyboard
from manashelper.config import Settings
from manashelper.db.models.advertisement import AdvertisementStatus
from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import DEFAULT_LOCALE
from manashelper.services.advertisement import (
    AdvertisementForbiddenError,
    AdvertisementMediaItem,
    AdvertisementNotFoundError,
    AdvertisementService,
    AdvertisementSummary,
    TooManyAdvertisementsError,
)
from manashelper.services.advertisement_formatter import build_media_group, format_advertisement
from manashelper.services.user_contact import (
    ContactStatus,
    InvalidPhoneNumberError,
    UserContactService,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)

router = Router(name="advertisement")

TITLE_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 512
MEDIA_PROMPT_MESSAGE_ID_KEY = "media_prompt_message_id"

EXPIRY_OPTION_TO_TIMEDELTA: dict[AdvertisementExpiryOption, timedelta | None] = {
    AdvertisementExpiryOption.MIN_45: timedelta(minutes=45),
    AdvertisementExpiryOption.HOURS_6: timedelta(hours=6),
    AdvertisementExpiryOption.HOURS_24: timedelta(hours=24),
    AdvertisementExpiryOption.DAYS_7: timedelta(days=7),
    AdvertisementExpiryOption.NONE: None,
}


class AdvertisementForm(StatesGroup):
    phone_number = State()
    title = State()
    description = State()
    price = State()
    media = State()
    expires_at = State()
    confirm = State()


def _draft_summary(data: dict[str, Any]) -> AdvertisementSummary:
    media_data: list[dict[str, str]] = data.get("media", [])
    media = [
        AdvertisementMediaItem(file_id=item["file_id"], media_type=AdvertisementMediaType(item["media_type"]))
        for item in media_data
    ]
    return AdvertisementSummary(
        id=uuid.uuid4(),
        user_id=0,
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        price=data.get("price"),
        status=AdvertisementStatus.PENDING,
        rejection_comment=None,
        expires_at=data.get("expires_at"),
        created_at=datetime.now(),
        media=media,
    )


async def _start_ad_details(message: Message, state: FSMContext) -> None:
    await state.set_state(AdvertisementForm.title)
    await message.answer(
        _(
            "📝 Let's create your ad.\n\n"
            "First, send a <b>title</b> (up to {max} characters) - this is the first thing buyers will see."
        ).format(max=TITLE_MAX_LENGTH),
        reply_markup=build_cancel_form_keyboard(),
    )


async def send_marketplace_menu(message: Message, settings: Settings) -> None:
    text = _(
        "🛒 <b>Marketplace</b>\n\n"
        "Post an ad for other students to see, or manage the ads you've already posted.\n\n"
        '🔗 <a href="{link}">Browse the marketplace channel</a>'
    ).format(link=settings.advertisement_channel_link)
    await message.answer(text, reply_markup=build_advertisement_menu_keyboard())


@router.message(TranslatedText("🛒 Marketplace"))
@flags.private_chat_only
async def on_marketplace_button(message: Message, settings: FromDishka[Settings]) -> None:
    await send_marketplace_menu(message, settings)


@router.message(TranslatedText("◀️ Back to menu"))
@flags.private_chat_only
async def on_back_to_main_menu(message: Message) -> None:
    await message.answer(_("🏠 Main menu"), reply_markup=build_main_keyboard())


@router.message(TranslatedText("➕ Post an ad"))
@flags.private_chat_only
async def on_create_requested(
    message: Message,
    state: FSMContext,
    advertisement_service: FromDishka[AdvertisementService],
    user_contact_service: FromDishka[UserContactService],
) -> None:
    if message.from_user is None:
        return
    user_id = message.from_user.id
    try:
        await advertisement_service.assert_can_post(user_id)
    except TooManyAdvertisementsError:
        await message.answer(_("You've posted the maximum of 5 ads for this hour. Please try again a bit later."))
        return

    try:
        contact = await user_contact_service.get_contact_status(user_id)
    except UserNotFoundError:
        await message.answer(_("Please start with the /start command"))
        return

    if contact.has_contact:
        await _start_ad_details(message, state)
    else:
        await state.set_state(AdvertisementForm.phone_number)
        await message.answer(
            _(
                "📞 Before you can post an ad, buyers need a way to reach you.\n\n"
                "You don't currently have a public Telegram username, so please share a phone number "
                "using the button below, or type one in manually (e.g. +996700123456):"
            ),
            reply_markup=build_contact_request_keyboard(),
        )


@router.message(F.contact, StateFilter(AdvertisementForm.phone_number))
@flags.private_chat_only
async def on_phone_number_shared(
    message: Message, state: FSMContext, user_contact_service: FromDishka[UserContactService]
) -> None:
    if message.contact is None or message.from_user is None:
        return
    try:
        await user_contact_service.add_phone_number(message.from_user.id, message.contact.phone_number)
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("Please start with the /start command"), reply_markup=ReplyKeyboardRemove())
        return
    except InvalidPhoneNumberError:
        # A shared Telegram contact's phone number is always well-formed - this shouldn't happen,
        # but if it somehow does, fall back to asking for manual entry instead of getting stuck.
        await message.answer(
            _("Something went wrong saving that number. Please type your phone number manually:"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await message.answer(_("✅ Phone number saved."), reply_markup=ReplyKeyboardRemove())
    await _start_ad_details(message, state)


@router.message(StateFilter(AdvertisementForm.phone_number))
@flags.private_chat_only
async def on_phone_number_entered(
    message: Message, state: FSMContext, user_contact_service: FromDishka[UserContactService]
) -> None:
    phone_number = message.text.strip() if message.text else ""
    if message.from_user is None:
        return
    try:
        await user_contact_service.add_phone_number(message.from_user.id, phone_number)
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("Please start with the /start command"), reply_markup=ReplyKeyboardRemove())
        return
    except InvalidPhoneNumberError:
        await message.answer(
            _("That doesn't look like a valid phone number (e.g. +996700123456). Please try again:"),
            reply_markup=build_contact_request_keyboard(),
        )
        return
    await message.answer(_("✅ Phone number saved."), reply_markup=ReplyKeyboardRemove())
    await _start_ad_details(message, state)


@router.message(StateFilter(AdvertisementForm.title))
@flags.private_chat_only
async def on_title_entered(message: Message, state: FSMContext) -> None:
    title = message.text.strip() if message.text else ""
    if not title or len(title) > TITLE_MAX_LENGTH:
        await message.answer(
            _("The title can't be empty and must be at most {max} characters long. Please try again:").format(
                max=TITLE_MAX_LENGTH
            ),
            reply_markup=build_cancel_form_keyboard(),
        )
        return

    await state.update_data(title=title)
    await state.set_state(AdvertisementForm.description)
    await message.answer(
        _(
            "🧾 Now send a <b>description</b> (up to {max} characters) - condition, size, reason for "
            "selling, anything a buyer should know."
        ).format(max=DESCRIPTION_MAX_LENGTH),
        reply_markup=build_cancel_form_keyboard(),
    )


@router.message(StateFilter(AdvertisementForm.description))
@flags.private_chat_only
async def on_description_entered(message: Message, state: FSMContext) -> None:
    description = message.text.strip() if message.text else ""
    if not description or len(description) > DESCRIPTION_MAX_LENGTH:
        await message.answer(
            _("The description can't be empty and must be at most {max} characters long. Please try again:").format(
                max=DESCRIPTION_MAX_LENGTH
            ),
            reply_markup=build_cancel_form_keyboard(),
        )
        return

    await state.update_data(description=description)
    await state.set_state(AdvertisementForm.price)
    await message.answer(
        _("💵 Send the price in som (digits only), or tap Skip if it's negotiable or not applicable:"),
        reply_markup=build_skip_price_keyboard(),
    )


async def _enter_media_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.media)
    text = _(
        "🖼 Send up to 10 photos or videos of the item, one at a time.\n\n"
        "Tap Done when you're finished - or tap it right away to post without media."
    )
    if edit:
        await target.edit_text(text, reply_markup=build_media_keyboard())
    else:
        await target.answer(text, reply_markup=build_media_keyboard())


@router.message(StateFilter(AdvertisementForm.price))
@flags.private_chat_only
async def on_price_entered(message: Message, state: FSMContext) -> None:
    price_text = message.text.strip() if message.text else ""
    if not price_text.isdigit():
        await message.answer(
            _("Please send a whole number (digits only), or tap Skip:"), reply_markup=build_skip_price_keyboard()
        )
        return

    await state.update_data(price=int(price_text))
    await _enter_media_state(message, state, edit=False)


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.SKIP_PRICE))
@flags.private_chat_only
async def on_price_skipped(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(price=None)
    if isinstance(callback_query.message, Message):
        await _enter_media_state(callback_query.message, state, edit=True)
    await callback_query.answer()


@router.message(StateFilter(AdvertisementForm.media), F.photo)
@flags.private_chat_only
async def on_media_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.photo is None:
        return
    await _append_media(message, state, bot, message.photo[-1].file_id, AdvertisementMediaType.PHOTO)


@router.message(StateFilter(AdvertisementForm.media), F.video)
@flags.private_chat_only
async def on_media_video(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.video is None:
        return
    await _append_media(message, state, bot, message.video.file_id, AdvertisementMediaType.VIDEO)


async def _render_media_prompt(message: Message, state: FSMContext, bot: Bot, text: str) -> None:
    """Renders the running media-count prompt by editing the *same* message in place, rather than
    sending a fresh one for every photo/video - otherwise posting a 10-item album would spam the
    chat with 10 separate confirmation messages. Safe to edit repeatedly without any debounce/race
    handling: `PerChatOrderingMiddleware` already serializes every update for this chat, so the
    album's messages are guaranteed to be processed one at a time, in order."""
    data = await state.get_data()
    prompt_message_id = data.get(MEDIA_PROMPT_MESSAGE_ID_KEY)
    if prompt_message_id is not None:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id, message_id=prompt_message_id, text=text, reply_markup=build_media_keyboard()
            )
            return
        except TelegramBadRequest:
            pass  # the prompt message was likely deleted by hand - fall back to sending a new one

    sent = await message.answer(text, reply_markup=build_media_keyboard())
    await state.update_data({MEDIA_PROMPT_MESSAGE_ID_KEY: sent.message_id})


async def _append_media(
    message: Message, state: FSMContext, bot: Bot, file_id: str, media_type: AdvertisementMediaType
) -> None:
    data = await state.get_data()
    media: list[dict[str, str]] = list(data.get("media", []))
    if len(media) >= AdvertisementService.MAX_MEDIA_ITEMS:
        await _render_media_prompt(
            message,
            state,
            bot,
            _("You've reached the limit of {max} photos/videos. Tap Done to continue.").format(
                max=AdvertisementService.MAX_MEDIA_ITEMS
            ),
        )
        return

    media.append({"file_id": file_id, "media_type": media_type.value})
    await state.update_data(media=media)
    await _render_media_prompt(
        message,
        state,
        bot,
        _("✅ Added: {count}/{max}. Send more, or tap Done when you're finished.").format(
            count=len(media), max=AdvertisementService.MAX_MEDIA_ITEMS
        ),
    )


async def _enter_expiry_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.expires_at)
    text = _("⏳ How long should this ad stay visible before it's automatically removed?")
    if edit:
        await target.edit_text(text, reply_markup=build_expiry_keyboard())
    else:
        await target.answer(text, reply_markup=build_expiry_keyboard())


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.DONE_MEDIA))
@flags.private_chat_only
async def on_media_done(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data({MEDIA_PROMPT_MESSAGE_ID_KEY: None})
    if isinstance(callback_query.message, Message):
        await _enter_expiry_state(callback_query.message, state, edit=True)
    await callback_query.answer()


@router.callback_query(AdvertisementExpiryCallback.filter())
@flags.private_chat_only
async def on_expiry_selected(
    callback_query: CallbackQuery, callback_data: AdvertisementExpiryCallback, state: FSMContext
) -> None:
    delta = EXPIRY_OPTION_TO_TIMEDELTA[callback_data.option]
    await state.update_data(expires_at=datetime.now() + delta if delta is not None else None)
    if isinstance(callback_query.message, Message):
        await _enter_confirm_state(callback_query.message, state, edit=True)
    await callback_query.answer()


async def _enter_confirm_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.confirm)
    data = await state.get_data()
    preview = _draft_summary(data)
    text = _("👀 Here's how your ad will look:") + "\n\n" + format_advertisement(preview)
    if edit:
        await target.edit_text(text, reply_markup=build_confirm_keyboard())
    else:
        await target.answer(text, reply_markup=build_confirm_keyboard())


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.CANCEL))
@flags.private_chat_only
async def on_form_cancelled(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("❌ Cancelled."))
    await callback_query.answer()


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.CONFIRM_SUBMIT))
@flags.private_chat_only
async def on_form_submitted(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    advertisement_service: FromDishka[AdvertisementService],
    user_contact_service: FromDishka[UserContactService],
) -> None:
    user_id = callback_query.from_user.id
    data = await state.get_data()
    media_data: list[dict[str, str]] = data.get("media", [])
    media_items = [
        AdvertisementMediaItem(file_id=item["file_id"], media_type=AdvertisementMediaType(item["media_type"]))
        for item in media_data
    ]

    try:
        summary = await advertisement_service.create_advertisement(
            user_id=user_id,
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            price=data.get("price"),
            expires_at=data.get("expires_at"),
            media_items=media_items,
        )
    except TooManyAdvertisementsError:
        await callback_query.answer(
            _("You've posted the maximum of 5 ads for this hour. Please try again a bit later."), show_alert=True
        )
        return

    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("✅ Your ad has been sent for moderator review. You'll be notified once it's approved or rejected.")
        )
        await send_marketplace_menu(callback_query.message, settings)

    contact = await user_contact_service.get_contact_status(user_id)
    await _notify_moderation_chat(bot, settings, summary, contact)


async def _notify_moderation_chat(
    bot: Bot, settings: Settings, summary: AdvertisementSummary, contact: ContactStatus
) -> None:
    """Sent to the single shared `Settings.moderation_chat_id`, not to individual moderators - there
    is no per-user moderator role, so (like the channel) this always renders in `DEFAULT_LOCALE`
    rather than any one recipient's locale."""
    with i18n.context(), i18n.use_locale(DEFAULT_LOCALE.value):
        caption = _("🆕 <b>New ad for review</b>") + "\n\n" + format_advertisement(summary, contact=contact)
        keyboard = build_moderation_keyboard(summary.id)
        review_text = _("Review it:")
    try:
        if summary.media:
            await bot.send_media_group(
                chat_id=settings.moderation_chat_id, media=build_media_group(caption, summary.media)
            )
            await bot.send_message(chat_id=settings.moderation_chat_id, text=review_text, reply_markup=keyboard)
        else:
            await bot.send_message(chat_id=settings.moderation_chat_id, text=caption, reply_markup=keyboard)
    except TelegramAPIError:
        logger.warning("Failed to notify the moderation chat about a new ad", exc_info=True)


@router.message(TranslatedText("📋 My ads"))
@flags.private_chat_only
async def on_my_ads_requested(message: Message, advertisement_service: FromDishka[AdvertisementService]) -> None:
    if message.from_user is None:
        return
    text, keyboard = await _build_my_ads_view(advertisement_service, message.from_user.id, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(AdvertisementsPageCallback.filter())
@flags.private_chat_only
async def on_my_ads_page(
    callback_query: CallbackQuery,
    callback_data: AdvertisementsPageCallback,
    advertisement_service: FromDishka[AdvertisementService],
) -> None:
    text, keyboard = await _build_my_ads_view(advertisement_service, callback_query.from_user.id, callback_data.page)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def _build_my_ads_view(
    advertisement_service: AdvertisementService, user_id: int, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    ad_page = await advertisement_service.get_page_by_user_id(user_id, page)
    text = _("📋 <b>My ads</b> (page {page}/{total})").format(page=ad_page.page + 1, total=ad_page.total_pages)
    if not ad_page.items:
        text = _("📋 <b>My ads</b>\n\nYou haven't posted any ads yet.")
    keyboard = build_my_ads_keyboard(ad_page.items, ad_page.page, ad_page.total_pages)
    return text, keyboard


@router.callback_query(AdvertisementCallback.filter())
@flags.private_chat_only
async def on_advertisement_selected(
    callback_query: CallbackQuery,
    callback_data: AdvertisementCallback,
    advertisement_service: FromDishka[AdvertisementService],
) -> None:
    await _render_advertisement_detail(callback_query, advertisement_service, callback_data.id, callback_data.page)


async def _render_advertisement_detail(
    callback_query: CallbackQuery, advertisement_service: AdvertisementService, advertisement_id: uuid.UUID, page: int
) -> None:
    try:
        summary = await advertisement_service.get_owned_by_id(advertisement_id, callback_query.from_user.id)
    except (AdvertisementNotFoundError, AdvertisementForbiddenError):
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return

    text = format_advertisement(summary, show_status=True)
    keyboard = build_advertisement_detail_keyboard(summary.id, page)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


@router.callback_query(AdvertisementDeleteCallback.filter(F.action == AdvertisementDeleteAction.REQUEST))
@flags.private_chat_only
async def on_delete_requested(callback_query: CallbackQuery, callback_data: AdvertisementDeleteCallback) -> None:
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(
            _("Are you sure you want to delete this ad? This can't be undone."),
            reply_markup=build_advertisement_delete_confirm_keyboard(callback_data.id, callback_data.page),
        )
    await callback_query.answer()


@router.callback_query(AdvertisementDeleteCallback.filter(F.action == AdvertisementDeleteAction.CANCEL))
@flags.private_chat_only
async def on_delete_cancelled(
    callback_query: CallbackQuery,
    callback_data: AdvertisementDeleteCallback,
    advertisement_service: FromDishka[AdvertisementService],
) -> None:
    await _render_advertisement_detail(callback_query, advertisement_service, callback_data.id, callback_data.page)


@router.callback_query(AdvertisementDeleteCallback.filter(F.action == AdvertisementDeleteAction.CONFIRM))
@flags.private_chat_only
async def on_delete_confirmed(
    callback_query: CallbackQuery,
    callback_data: AdvertisementDeleteCallback,
    bot: Bot,
    settings: FromDishka[Settings],
    advertisement_service: FromDishka[AdvertisementService],
) -> None:
    try:
        result = await advertisement_service.delete_owned(callback_data.id, callback_query.from_user.id)
    except (AdvertisementNotFoundError, AdvertisementForbiddenError):
        await callback_query.answer(_("This ad no longer exists"), show_alert=True)
        return

    if result.channel_message_ids:
        try:
            await bot.delete_messages(chat_id=settings.advertisement_channel_id, message_ids=result.channel_message_ids)
        except TelegramAPIError:
            logger.warning("Failed to delete channel messages for advertisement %s", callback_data.id, exc_info=True)

    ad_page = await advertisement_service.get_page_by_user_id(callback_query.from_user.id, callback_data.page)
    text = _("Ad deleted ✅")
    keyboard = build_my_ads_keyboard(ad_page.items, ad_page.page, ad_page.total_pages)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()
