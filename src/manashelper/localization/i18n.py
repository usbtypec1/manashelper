from collections.abc import Generator
from contextlib import contextmanager
from gettext import GNUTranslations
from pathlib import Path

from aiogram.utils.i18n import I18n

from manashelper.localization.locale import DEFAULT_LOCALE, Locale


class CatalogI18n(I18n):
    """Resolve message keys through catalogs, with English as the translation fallback."""

    @contextmanager
    def context(self) -> Generator[I18n]:
        # Aiogram's gettext helpers read the base I18n context, whereas its mixin gives
        # each subclass a separate context variable.
        token = I18n.set_current(self)
        try:
            yield self
        finally:
            I18n.reset_current(token)

    def find_locales(self) -> dict[str, GNUTranslations]:
        translations = super().find_locales()
        english = translations[Locale.EN.value]
        for locale, translation in translations.items():
            if locale != Locale.EN.value:
                translation.add_fallback(english)
        return translations

    def gettext(self, singular: str, plural: str | None = None, n: int = 1, locale: str | None = None) -> str:
        resolved_locale = locale if locale is not None else self.current_locale
        if resolved_locale not in self.locales:
            resolved_locale = Locale.EN.value
        return super().gettext(singular, plural, n, resolved_locale)


i18n = CatalogI18n(path=Path(__file__).resolve().parent.parent / "locales", default_locale=DEFAULT_LOCALE.value)
