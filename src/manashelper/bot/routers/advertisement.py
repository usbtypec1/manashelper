import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot, F, Router, flags
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    AdvertisementCallback,
    AdvertisementDeleteAction,
    AdvertisementDeleteCallback,
    AdvertisementFormAction,
    AdvertisementFormCallback,
    AdvertisementMenuAction,
    AdvertisementMenuCallback,
    AdvertisementsPageCallback,
)
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.advertisement import (
    build_advertisement_delete_confirm_keyboard,
    build_advertisement_detail_keyboard,
    build_advertisement_menu_keyboard,
    build_cancel_form_keyboard,
    build_confirm_keyboard,
    build_contact_request_keyboard,
    build_media_keyboard,
    build_my_ads_keyboard,
    build_skip_expires_at_keyboard,
    build_skip_price_keyboard,
)
from manashelper.bot.keyboards.advertisement_moderation import build_moderation_keyboard
from manashelper.bot.routers.start import build_main_keyboard
from manashelper.config import Settings
from manashelper.db.models.advertisement import AdvertisementStatus
from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.localization.i18n import i18n
from manashelper.services.advertisement import (
    AdvertisementForbiddenError,
    AdvertisementMediaItem,
    AdvertisementNotFoundError,
    AdvertisementService,
    AdvertisementSummary,
    TooManyAdvertisementsError,
)
from manashelper.services.advertisement_formatter import build_media_group, format_advertisement
from manashelper.services.advertisement_moderation import AdvertisementModerationService
from manashelper.services.locale import LocaleService
from manashelper.services.user_contact import ContactStatus, UserContactService, UserNotFoundError

logger = logging.getLogger(__name__)

router = Router(name="advertisement")

TITLE_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 512
PHONE_NUMBER_PATTERN = re.compile(r"^\+?\d[\d\s\-()]{5,19}$")


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
        _("Let's create your ad. Enter a title (up to {max} characters):").format(max=TITLE_MAX_LENGTH),
        reply_markup=build_cancel_form_keyboard(),
    )


@router.message(TranslatedText("🛒 Marketplace"))
@flags.private_chat_only
async def on_marketplace_button(message: Message) -> None:
    await message.answer(_("🛒 <b>Marketplace</b>"), reply_markup=build_advertisement_menu_keyboard())


@router.callback_query(AdvertisementMenuCallback.filter(F.action == AdvertisementMenuAction.CREATE))
@flags.private_chat_only
async def on_create_requested(
    callback_query: CallbackQuery,
    state: FSMContext,
    advertisement_service: FromDishka[AdvertisementService],
    user_contact_service: FromDishka[UserContactService],
) -> None:
    user_id = callback_query.from_user.id
    try:
        await advertisement_service.assert_can_post(user_id)
    except TooManyAdvertisementsError:
        await callback_query.answer(
            _("You've posted too many ads in the last hour. Please try again later."), show_alert=True
        )
        return

    try:
        contact = await user_contact_service.get_contact_status(user_id)
    except UserNotFoundError:
        await callback_query.answer(_("Please start with the /start command"), show_alert=True)
        return

    if isinstance(callback_query.message, Message):
        if contact.has_contact:
            await _start_ad_details(callback_query.message, state)
        else:
            await state.set_state(AdvertisementForm.phone_number)
            await callback_query.message.answer(
                _(
                    "To post an ad you need at least one contact method (a Telegram username or a phone "
                    "number). You don't have a public username, so please share a phone number using the "
                    "button below, or type it manually:"
                ),
                reply_markup=build_contact_request_keyboard(),
            )
    await callback_query.answer()


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
    await message.answer(_("Phone number saved ✅"), reply_markup=ReplyKeyboardRemove())
    await _start_ad_details(message, state)


@router.message(StateFilter(AdvertisementForm.phone_number))
@flags.private_chat_only
async def on_phone_number_entered(
    message: Message, state: FSMContext, user_contact_service: FromDishka[UserContactService]
) -> None:
    phone_number = message.text.strip() if message.text else ""
    if not PHONE_NUMBER_PATTERN.match(phone_number):
        await message.answer(
            _("That doesn't look like a valid phone number. Please try again:"),
            reply_markup=build_contact_request_keyboard(),
        )
        return

    if message.from_user is None:
        return
    try:
        await user_contact_service.add_phone_number(message.from_user.id, phone_number)
    except UserNotFoundError:
        await state.clear()
        await message.answer(_("Please start with the /start command"), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(_("Phone number saved ✅"), reply_markup=ReplyKeyboardRemove())
    await _start_ad_details(message, state)


@router.message(StateFilter(AdvertisementForm.title))
@flags.private_chat_only
async def on_title_entered(message: Message, state: FSMContext) -> None:
    title = message.text.strip() if message.text else ""
    if not title or len(title) > TITLE_MAX_LENGTH:
        await message.answer(
            _("The title can't be empty and must be at most {max} characters. Please try again:").format(
                max=TITLE_MAX_LENGTH
            ),
            reply_markup=build_cancel_form_keyboard(),
        )
        return

    await state.update_data(title=title)
    await state.set_state(AdvertisementForm.description)
    await message.answer(
        _("Enter a description (up to {max} characters):").format(max=DESCRIPTION_MAX_LENGTH),
        reply_markup=build_cancel_form_keyboard(),
    )


@router.message(StateFilter(AdvertisementForm.description))
@flags.private_chat_only
async def on_description_entered(message: Message, state: FSMContext) -> None:
    description = message.text.strip() if message.text else ""
    if not description or len(description) > DESCRIPTION_MAX_LENGTH:
        await message.answer(
            _("The description can't be empty and must be at most {max} characters. Please try again:").format(
                max=DESCRIPTION_MAX_LENGTH
            ),
            reply_markup=build_cancel_form_keyboard(),
        )
        return

    await state.update_data(description=description)
    await state.set_state(AdvertisementForm.price)
    await message.answer(
        _("Enter a price in som, or tap Skip:"),
        reply_markup=build_skip_price_keyboard(),
    )


async def _enter_media_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.media)
    text = _("Send up to 10 photos or videos, then tap Done. Or tap Done right away to skip.")
    if edit:
        await target.edit_text(text, reply_markup=build_media_keyboard())
    else:
        await target.answer(text, reply_markup=build_media_keyboard())


@router.message(StateFilter(AdvertisementForm.price))
@flags.private_chat_only
async def on_price_entered(message: Message, state: FSMContext) -> None:
    price_text = message.text.strip() if message.text else ""
    if not price_text.isdigit():
        await message.answer(_("Please enter a whole number, or tap Skip:"), reply_markup=build_skip_price_keyboard())
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
async def on_media_photo(message: Message, state: FSMContext) -> None:
    if message.photo is None:
        return
    await _append_media(message, state, message.photo[-1].file_id, AdvertisementMediaType.PHOTO)


@router.message(StateFilter(AdvertisementForm.media), F.video)
@flags.private_chat_only
async def on_media_video(message: Message, state: FSMContext) -> None:
    if message.video is None:
        return
    await _append_media(message, state, message.video.file_id, AdvertisementMediaType.VIDEO)


async def _append_media(message: Message, state: FSMContext, file_id: str, media_type: AdvertisementMediaType) -> None:
    data = await state.get_data()
    media: list[dict[str, str]] = list(data.get("media", []))
    if len(media) >= AdvertisementService.MAX_MEDIA_ITEMS:
        await message.answer(
            _("You've reached the limit of {max} photos/videos. Tap Done to continue.").format(
                max=AdvertisementService.MAX_MEDIA_ITEMS
            ),
            reply_markup=build_media_keyboard(),
        )
        return

    media.append({"file_id": file_id, "media_type": media_type.value})
    await state.update_data(media=media)
    await message.answer(
        _("Added ({count}/{max}). Send more, or tap Done.").format(
            count=len(media), max=AdvertisementService.MAX_MEDIA_ITEMS
        ),
        reply_markup=build_media_keyboard(),
    )


async def _enter_expires_at_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.expires_at)
    text = _("Enter an expiration date as DD.MM.YYYY, or tap Skip for no expiration:")
    if edit:
        await target.edit_text(text, reply_markup=build_skip_expires_at_keyboard())
    else:
        await target.answer(text, reply_markup=build_skip_expires_at_keyboard())


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.DONE_MEDIA))
@flags.private_chat_only
async def on_media_done(callback_query: CallbackQuery, state: FSMContext) -> None:
    if isinstance(callback_query.message, Message):
        await _enter_expires_at_state(callback_query.message, state, edit=True)
    await callback_query.answer()


@router.message(StateFilter(AdvertisementForm.expires_at))
@flags.private_chat_only
async def on_expires_at_entered(message: Message, state: FSMContext) -> None:
    text = message.text.strip() if message.text else ""
    try:
        parsed = datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        await message.answer(
            _("That doesn't look like a valid date. Please use DD.MM.YYYY, or tap Skip:"),
            reply_markup=build_skip_expires_at_keyboard(),
        )
        return

    expires_at = parsed + timedelta(hours=23, minutes=59)
    if expires_at <= datetime.now():
        await message.answer(
            _("The expiration date must be in the future. Please try again, or tap Skip:"),
            reply_markup=build_skip_expires_at_keyboard(),
        )
        return

    await state.update_data(expires_at=expires_at)
    await _enter_confirm_state(message, state, edit=False)


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.SKIP_EXPIRES_AT))
@flags.private_chat_only
async def on_expires_at_skipped(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(expires_at=None)
    if isinstance(callback_query.message, Message):
        await _enter_confirm_state(callback_query.message, state, edit=True)
    await callback_query.answer()


async def _enter_confirm_state(target: Message, state: FSMContext, *, edit: bool) -> None:
    await state.set_state(AdvertisementForm.confirm)
    data = await state.get_data()
    preview = _draft_summary(data)
    text = _("Please review your ad:") + "\n\n" + format_advertisement(preview)
    if edit:
        await target.edit_text(text, reply_markup=build_confirm_keyboard())
    else:
        await target.answer(text, reply_markup=build_confirm_keyboard())


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.CANCEL))
@flags.private_chat_only
async def on_form_cancelled(callback_query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Cancelled"))
    await callback_query.answer()


@router.callback_query(AdvertisementFormCallback.filter(F.action == AdvertisementFormAction.CONFIRM_SUBMIT))
@flags.private_chat_only
async def on_form_submitted(
    callback_query: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: FromDishka[Settings],
    advertisement_service: FromDishka[AdvertisementService],
    moderation_service: FromDishka[AdvertisementModerationService],
    user_contact_service: FromDishka[UserContactService],
    locale_service: FromDishka[LocaleService],
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
            _("You've posted too many ads in the last hour. Please try again later."), show_alert=True
        )
        return

    await state.clear()
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(_("Your ad has been submitted for review ✅"))
        await callback_query.message.answer(_("🛒 <b>Marketplace</b>"), reply_markup=build_main_keyboard())

    contact = await user_contact_service.get_contact_status(user_id)
    await _notify_moderators(bot, moderation_service, locale_service, summary, contact)


async def _notify_moderators(
    bot: Bot,
    moderation_service: AdvertisementModerationService,
    locale_service: LocaleService,
    summary: AdvertisementSummary,
    contact: ContactStatus,
) -> None:
    moderator_ids = await moderation_service.get_moderator_ids()
    for moderator_id in moderator_ids:
        locale = await locale_service.get_locale(moderator_id)
        with i18n.context(), i18n.use_locale(locale.value):
            caption = _("🆕 <b>New ad for review</b>") + "\n\n" + format_advertisement(summary, contact=contact)
            keyboard = build_moderation_keyboard(summary.id)
        try:
            if summary.media:
                await bot.send_media_group(chat_id=moderator_id, media=build_media_group(caption, summary.media))
                await bot.send_message(chat_id=moderator_id, text=_("Review it:"), reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=moderator_id, text=caption, reply_markup=keyboard)
        except TelegramAPIError:
            logger.warning("Failed to notify moderator %s about a new ad", moderator_id, exc_info=True)


@router.callback_query(AdvertisementMenuCallback.filter(F.action == AdvertisementMenuAction.MY_ADS))
@flags.private_chat_only
async def on_my_ads_requested(
    callback_query: CallbackQuery, advertisement_service: FromDishka[AdvertisementService]
) -> None:
    await _render_my_ads(callback_query, advertisement_service, 0)


@router.callback_query(AdvertisementsPageCallback.filter())
@flags.private_chat_only
async def on_my_ads_page(
    callback_query: CallbackQuery,
    callback_data: AdvertisementsPageCallback,
    advertisement_service: FromDishka[AdvertisementService],
) -> None:
    await _render_my_ads(callback_query, advertisement_service, callback_data.page)


async def _render_my_ads(callback_query: CallbackQuery, advertisement_service: AdvertisementService, page: int) -> None:
    ad_page = await advertisement_service.get_page_by_user_id(callback_query.from_user.id, page)
    text = _("📋 <b>My ads</b> (page {page}/{total})").format(page=ad_page.page + 1, total=ad_page.total_pages)
    if not ad_page.items:
        text = _("📋 <b>My ads</b>\n\nYou haven't posted any ads yet.")
    keyboard = build_my_ads_keyboard(ad_page.items, ad_page.page, ad_page.total_pages)
    if isinstance(callback_query.message, Message):
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


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
            _("Are you sure you want to delete this ad?"),
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
