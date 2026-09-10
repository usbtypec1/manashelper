from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import ObisAction, ObisCallback, SettingsAction, SettingsCallback

TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-manas-helper-bot-01-13"


def build_obis_settings_keyboard(has_credentials: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    credentials_text = "🔄 Обновить данные" if has_credentials else "🔑 Ввести данные"
    builder.button(text=credentials_text, callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    if has_credentials:
        builder.button(text="🗑 Очистить данные", callback_data=ObisCallback(action=ObisAction.CLEAR_CREDENTIALS))
    builder.button(text="◀️ Назад", callback_data=SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS))
    builder.adjust(1)
    return builder.as_markup()


def build_no_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔑 Ввести данные", callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_confirm_clear_credentials_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, очистить", callback_data=ObisCallback(action=ObisAction.CONFIRM_CLEAR_CREDENTIALS))
    builder.button(text="❌ Отмена", callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()


def build_terms_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📃 Условия использования", url=TERMS_URL)
    builder.button(text="✅ Принять условия", callback_data=ObisCallback(action=ObisAction.ACCEPT_TERMS))
    builder.adjust(1)
    return builder.as_markup()


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=ObisCallback(action=ObisAction.CANCEL_CREDENTIALS))
    builder.adjust(1)
    return builder.as_markup()
