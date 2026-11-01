from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.platform.telegram.keyboards.settings import build_settings_keyboard


async def show_settings(message: Message) -> None:
    await message.answer(_("settings.title"), reply_markup=build_settings_keyboard())
