from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.core.config import Settings
from manashelper.modules.advertisements.presentation.keyboards.advertisement import build_advertisement_menu_keyboard


async def send_marketplace_menu(message: Message, settings: Settings) -> None:
    text = _("ads.marketplace_intro").format(link=settings.advertisement_channel_link)
    await message.answer(text, reply_markup=build_advertisement_menu_keyboard())
