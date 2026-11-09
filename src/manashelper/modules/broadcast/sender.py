from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from manashelper.modules.broadcast.keyboards import build_broadcast_delivery_keyboard
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from manashelper.platform.telegram.outbox.service import OutboxService, OutgoingMethod


class TelegramBroadcastSender:
    def __init__(
        self,
        outbox: OutboxService,
        locales: LocaleQuery,
        themes: ThemeQuery,
        *,
        photo_id: str | None = None,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> None:
        self._outbox = outbox
        self._locales = locales
        self._themes = themes
        self._photo_id = photo_id
        self._keyboard = keyboard

    async def send(self, user_id: int, body: str) -> bool:
        locale = await self._locales.get_locale(user_id)
        theme = await self._themes.get_theme(user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            keyboard = build_broadcast_delivery_keyboard(self._keyboard)
            text = _("broadcast.admin_message").format(body=escape_html(body))
            caption_fits = len(_("broadcast.admin_message").format(body=body).encode("utf-16-le")) // 2 <= 1024
        methods: list[OutgoingMethod] = []
        if self._photo_id is not None:
            methods.append(
                SendPhoto(
                    chat_id=user_id,
                    photo=self._photo_id,
                    caption=text if caption_fits else None,
                    reply_markup=keyboard if caption_fits else None,
                )
            )
        if self._photo_id is None or not caption_fits:
            methods.append(SendMessage(chat_id=user_id, text=text, reply_markup=keyboard))
        return await self._outbox.enqueue(user_id, methods, category="broadcast")
