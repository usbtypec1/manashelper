import uuid

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import AdvertisementModerationAction, AdvertisementModerationCallback


def build_moderation_keyboard(advertisement_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("✅ Approve"),
        callback_data=AdvertisementModerationCallback(
            id=advertisement_id, action=AdvertisementModerationAction.APPROVE
        ),
    )
    builder.button(
        text=_("❌ Reject"),
        callback_data=AdvertisementModerationCallback(id=advertisement_id, action=AdvertisementModerationAction.REJECT),
    )
    builder.adjust(2)
    return builder.as_markup()


def build_reject_comment_choice_keyboard(advertisement_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("✏️ Add a comment"),
        callback_data=AdvertisementModerationCallback(
            id=advertisement_id, action=AdvertisementModerationAction.ADD_COMMENT
        ),
    )
    builder.button(
        text=_("🚫 No comment"),
        callback_data=AdvertisementModerationCallback(
            id=advertisement_id, action=AdvertisementModerationAction.SKIP_COMMENT
        ),
    )
    builder.adjust(1)
    return builder.as_markup()
