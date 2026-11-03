from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.modules.broadcast.callbacks import BroadcastAction, BroadcastCallback
from manashelper.modules.broadcast.content import BroadcastButton
from manashelper.modules.notifications.callbacks import BroadcastMuteCallback


def build_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=_("common.send"), callback_data=BroadcastCallback(action=BroadcastAction.CONFIRM))
    builder.button(text=_("common.cancel"), callback_data=BroadcastCallback(action=BroadcastAction.CANCEL))
    builder.button(text=_("broadcast.edit_buttons"), callback_data=BroadcastCallback(action=BroadcastAction.BUTTONS))
    builder.adjust(2, 1)
    return builder.as_markup()


def build_broadcast_buttons(buttons: list[BroadcastButton]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.button(text=button.text, url=button.url, callback_data=button.callback_data)
    builder.adjust(1)
    return builder.as_markup()


def build_broadcast_buttons_editor() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("broadcast.without_buttons"), callback_data=BroadcastCallback(action=BroadcastAction.WITHOUT_BUTTONS)
    )
    builder.button(text=_("common.cancel"), callback_data=BroadcastCallback(action=BroadcastAction.CANCEL))
    builder.adjust(1)
    return builder.as_markup()


def build_broadcast_delivery_keyboard(keyboard: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    rows = [list(row) for row in keyboard.inline_keyboard] if keyboard else []
    rows.append(
        [
            InlineKeyboardButton(
                text=_("notifications.mute_broadcasts"), callback_data=BroadcastMuteCallback(muted=True).pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
