from aiogram.filters import Filter
from aiogram.types import Message
from aiogram.utils.i18n import gettext as _


class TranslatedText(Filter):
    """Matches a message's text against a source string translated in the user's own locale.

    Reply-keyboard buttons echo their label back as the message text when tapped, and that
    label is localized per user, so a plain `F.text == "..."` filter can't match every locale
    at once — this compares against `_(source_text)` instead, resolved via the gettext context
    `LocaleMiddleware` activates for the current update.
    """

    def __init__(self, source_text: str) -> None:
        self.source_text = source_text

    async def __call__(self, message: Message) -> bool:
        return message.text == _(self.source_text)
