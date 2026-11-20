from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.broadcast.application.campaigns import CampaignDraft
from manashelper.modules.broadcast.keyboards import build_broadcast_delivery_keyboard
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.html import escape_html
from manashelper.platform.telegram.outbox.service import OutboxService, OutgoingMethod


def broadcast_body_fits(body: str) -> bool:
    for locale in Locale:
        for theme in Theme:
            with i18n.use_theme(theme):
                preview = i18n.gettext("broadcast.preview", locale=locale.value).format(body=body)
                delivered = i18n.gettext("broadcast.admin_message", locale=locale.value).format(body=body)
                if max(len(preview.encode("utf-16-le")), len(delivered.encode("utf-16-le"))) // 2 > 4096:
                    return False
    return True


def build_broadcast_delivery(
    user_id: int,
    body: str,
    locale: Locale,
    theme: Theme,
    *,
    photo_id: str | None = None,
    keyboard: InlineKeyboardMarkup | None = None,
) -> list[OutgoingMethod]:
    with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
        delivery_keyboard = build_broadcast_delivery_keyboard(keyboard)
        text = _("broadcast.admin_message").format(body=escape_html(body))
        caption_fits = photo_id is not None and (
            len(_("broadcast.admin_message").format(body=body).encode("utf-16-le")) // 2 <= 1024
        )
    methods: list[OutgoingMethod] = []
    if photo_id is not None:
        methods.append(
            SendPhoto(
                chat_id=user_id,
                photo=photo_id,
                caption=text if caption_fits else None,
                reply_markup=delivery_keyboard if caption_fits else None,
            )
        )
    if not caption_fits:
        methods.append(SendMessage(chat_id=user_id, text=text, reply_markup=delivery_keyboard))
    return methods


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
        methods = build_broadcast_delivery(
            user_id, body, locale, theme, photo_id=self._photo_id, keyboard=self._keyboard
        )
        return await self._outbox.enqueue(user_id, methods, category="broadcast")


class TelegramCampaignDelivery:
    def __init__(self, outbox: OutboxService) -> None:
        self._outbox = outbox

    def enqueue(self, draft: CampaignDraft, recipients: list[tuple[int, Locale, Theme]]) -> None:
        content = draft.messages_by_preference()
        self._outbox.enqueue_batch(
            draft.id,
            (
                (user_id, build_broadcast_delivery(user_id, content[locale, theme], locale, theme))
                for user_id, locale, theme in recipients
                if draft.includes(user_id)
            ),
            category="broadcast",
        )
