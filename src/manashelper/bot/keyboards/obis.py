from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import ObisAction, ObisCallback

TERMS_URL = "https://telegra.ph/Polzovatelskoe-soglashenie-manas-helper-bot-01-13"


def build_obis_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Йоклама", callback_data=ObisCallback(action=ObisAction.ATTENDANCE))
    builder.button(text="💯 Оценки", callback_data=ObisCallback(action=ObisAction.EXAMS))
    builder.button(text="🔑 Ввести данные от OBIS", callback_data=ObisCallback(action=ObisAction.START_CREDENTIALS))
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
