import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.delivery import UserMessageDelivery
from manashelper.platform.telegram.html import escape_html

logger = logging.getLogger(__name__)


class TelegramBroadcastSender:
    def __init__(
        self,
        bot: Bot,
        locales: LocaleService,
        status: BotStatusService,
        *,
        photo_id: str | None = None,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> None:
        self._bot = bot
        self._locales = locales
        self._delivery = UserMessageDelivery(status)
        self._photo_id = photo_id
        self._keyboard = keyboard

    async def send(self, user_id: int, body: str) -> bool:
        locale = await self._locales.get_locale(user_id)
        with i18n.context(), i18n.use_locale(locale.value):
            text = _("broadcast.admin_message").format(body=escape_html(body))
            caption_fits = len(_("broadcast.admin_message").format(body=body).encode("utf-16-le")) // 2 <= 1024
        try:
            photo_id = self._photo_id
            if photo_id is not None:
                photo = await self._delivery.send(
                    user_id,
                    lambda: self._bot.send_photo(
                        chat_id=user_id,
                        photo=photo_id,
                        caption=text if caption_fits else None,
                        reply_markup=self._keyboard if caption_fits else None,
                    ),
                )
                if photo is None:
                    return False
                if caption_fits:
                    return True
            sent = await self._delivery.send(
                user_id, lambda: self._bot.send_message(chat_id=user_id, text=text, reply_markup=self._keyboard)
            )
        except TelegramAPIError:
            logger.warning("Failed to deliver broadcast to user %s", user_id, exc_info=True)
            return False
        return sent is not None
