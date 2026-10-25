import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.utils.i18n import gettext as _

from manashelper.localization.i18n import i18n
from manashelper.services.html_sanitization import escape_html
from manashelper.services.locale import LocaleService

logger = logging.getLogger(__name__)


class TelegramBroadcastSender:
    def __init__(self, bot: Bot, locales: LocaleService) -> None:
        self._bot = bot
        self._locales = locales

    async def send(self, user_id: int, body: str) -> bool:
        locale = await self._locales.get_locale(user_id)
        with i18n.context(), i18n.use_locale(locale.value):
            text = _("broadcast.admin_message").format(body=escape_html(body))
        try:
            await self._bot.send_message(chat_id=user_id, text=text)
        except TelegramAPIError:
            logger.warning("Failed to deliver broadcast to user %s", user_id, exc_info=True)
            return False
        return True
