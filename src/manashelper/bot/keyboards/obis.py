from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import ObisAction, ObisCallback, SettingsAction, SettingsCallback

TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-manas-helper-bot-01-13"


def build_obis_settings_keyboard(has_credentials: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    credentials_text = _("🔄 Update credentials") if has_credentials else _("🔑 Enter credentials")
    builder.button(text=credentials_text, callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    if has_credentials:
        builder.button(text=_("🗑 Clear credentials"), callback_data=ObisCallback(action=ObisAction.CLEAR_CREDENTIALS))
    builder.button(text=_("◀️ Back"), callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()


def build_no_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("🔑 Enter credentials"), callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_clear_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("✅ Yes, clear"), callback_data=ObisCallback(action=ObisAction.CONFIRM_CLEAR_CREDENTIALS))
    builder.button(text=_("❌ Cancel"), callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_terms_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("📃 Terms of use"), url=TERMS_URL)
    builder.button(text=_("✅ Accept terms"), callback_data=ObisCallback(action=ObisAction.ACCEPT_TERMS))
    builder.adjust(1)
    return builder.as_markup()


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("❌ Cancel"), callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()
