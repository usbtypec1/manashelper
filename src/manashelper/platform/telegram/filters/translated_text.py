from aiogram.filters import Filter
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _

from manashelper.localization.theme import Theme
from manashelper.platform.i18n.catalog import i18n


class TranslatedText(Filter):
    """Matches a reply button in the user's locale, accepting labels from either theme.

    Reply-keyboard buttons echo their label back as the message text when tapped, and that
    label is localized per user, so a plain `F.text == "..."` filter can't match every locale
    at once — this compares against `_(message_key)` instead, resolved via the gettext context
    `LocaleMiddleware` activates for the current update.
    """

    def __init__(self, message_key: str) -> None:
        self.message_key = message_key

    async def __call__(self, message: Message) -> bool:
        # Telegram can still show a keyboard created before the theme was switched.
        for theme in Theme:
            with i18n.use_theme(theme):
                if message.text == _(self.message_key):
                    return True
        return False
