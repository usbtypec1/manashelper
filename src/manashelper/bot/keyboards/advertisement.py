import uuid

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
from manashelper.services.advertisement import AdvertisementSummary
from manashelper.services.advertisement_formatter import status_emoji

ADS_PER_ROW = 1


def build_advertisement_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("➕ Post an ad"), callback_data=AdvertisementMenuCallback(action=AdvertisementMenuAction.CREATE)
    )
    builder.button(text=_("📋 My ads"), callback_data=AdvertisementMenuCallback(action=AdvertisementMenuAction.MY_ADS))
    builder.adjust(1)
    return builder.as_markup()


def build_cancel_form_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("❌ Cancel"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CANCEL))
    return builder.as_markup()


def build_contact_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("📱 Share phone number"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_skip_price_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("Skip"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.SKIP_PRICE))
    builder.button(text=_("❌ Cancel"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CANCEL))
    builder.adjust(1)
    return builder.as_markup()


def build_media_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("✅ Done"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.DONE_MEDIA)
    )
    builder.button(text=_("❌ Cancel"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CANCEL))
    builder.adjust(1)
    return builder.as_markup()


def build_skip_expires_at_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("No expiration date"),
        callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.SKIP_EXPIRES_AT),
    )
    builder.button(text=_("❌ Cancel"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CANCEL))
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("✅ Submit for review"),
        callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CONFIRM_SUBMIT),
    )
    builder.button(text=_("❌ Cancel"), callback_data=AdvertisementFormCallback(action=AdvertisementFormAction.CANCEL))
    builder.adjust(1)
    return builder.as_markup()


def build_my_ads_keyboard(items: list[AdvertisementSummary], page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for advertisement in items:
        builder.button(
            text=f"{status_emoji(advertisement.status.value)} {advertisement.title}",
            callback_data=AdvertisementCallback(id=advertisement.id, page=page),
        )
    builder.adjust(ADS_PER_ROW)

    if total_pages > 1:
        nav_builder = InlineKeyboardBuilder()
        if page > 0:
            nav_builder.button(text="⬅️", callback_data=AdvertisementsPageCallback(page=page - 1))
        if page < total_pages - 1:
            nav_builder.button(text="➡️", callback_data=AdvertisementsPageCallback(page=page + 1))
        nav_builder.adjust(2)
        builder.attach(nav_builder)

    return builder.as_markup()


def build_advertisement_detail_keyboard(advertisement_id: uuid.UUID, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("🗑 Delete"),
        callback_data=AdvertisementDeleteCallback(
            id=advertisement_id, action=AdvertisementDeleteAction.REQUEST, page=page
        ),
    )
    builder.button(text=_("◀️ Back"), callback_data=AdvertisementsPageCallback(page=page))
    builder.adjust(1)
    return builder.as_markup()


def build_advertisement_delete_confirm_keyboard(advertisement_id: uuid.UUID, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("✅ Yes, delete"),
        callback_data=AdvertisementDeleteCallback(
            id=advertisement_id, action=AdvertisementDeleteAction.CONFIRM, page=page
        ),
    )
    builder.button(
        text=_("❌ Cancel"),
        callback_data=AdvertisementDeleteCallback(
            id=advertisement_id, action=AdvertisementDeleteAction.CANCEL, page=page
        ),
    )
    builder.adjust(1)
    return builder.as_markup()
