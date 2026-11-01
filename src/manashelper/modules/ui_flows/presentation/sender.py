from aiogram import Bot
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.i18n import gettext as _

from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.navigation import build_main_keyboard
from ui_flows.domain.delivery import ScreenDelivery


async def send_screen(bot: Bot, delivery: ScreenDelivery) -> int:
    screen = delivery.screen
    markup: ReplyKeyboardMarkup | ReplyKeyboardRemove
    if screen.keyboard == "reply":
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=button.label) for button in row] for row in screen.buttons],
            resize_keyboard=True,
        )
    elif screen.keyboard == "main":
        with i18n.context(), i18n.use_locale(screen.locale), i18n.use_theme(Theme(screen.theme)):
            markup = build_main_keyboard()
    else:
        markup = ReplyKeyboardRemove()
    message = await bot.send_message(delivery.chat_id, screen.text, reply_markup=markup, parse_mode="HTML")
    if screen.keyboard == "inline" and screen.buttons:
        index = 0
        rows = []
        for row in screen.buttons:
            buttons = []
            for button in row:
                payload = None if button.url is not None else UiFlowCallback(token=delivery.token, index=index).pack()
                buttons.append(InlineKeyboardButton(text=button.label, url=button.url, callback_data=payload))
                index += 1
            rows.append(buttons)
        # Telegram cannot edit a message sent with ReplyKeyboardRemove. Send the buttons directly.
        with i18n.context(), i18n.use_locale(screen.locale), i18n.use_theme(Theme(screen.theme)):
            actions = _("ui_flows.choose_action")
        message = await bot.send_message(
            delivery.chat_id, actions, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
        )
    return message.message_id
