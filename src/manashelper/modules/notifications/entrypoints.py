from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.modules.notifications.keyboards import build_notifications_keyboard
from manashelper.modules.notifications.settings import NotificationSettingsService


async def show_notifications(message: Message, user_id: int, settings: NotificationSettingsService) -> None:
    summary = await settings.get_settings(user_id)
    await message.answer(_("notifications.title"), reply_markup=build_notifications_keyboard(summary))
