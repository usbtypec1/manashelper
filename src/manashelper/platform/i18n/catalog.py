from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial
from gettext import GNUTranslations
from pathlib import Path

from aiogram.utils.i18n import I18n

from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.localization.theme import Theme
from manashelper.platform.i18n.themes import decorate_translation, halloween_translation


class CatalogI18n(I18n):
    """Resolve message keys through catalogs, with English as the translation fallback."""

    _theme: ContextVar[Theme] = ContextVar("theme", default=Theme.BASIC)

    @property
    def current_theme(self) -> Theme:
        return self._theme.get()

    @contextmanager
    def use_theme(self, theme: Theme) -> Generator[None]:
        token = self._theme.set(theme)
        try:
            yield
        finally:
            self._theme.reset(token)

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
        if self.current_theme == Theme.HALLOWEEN:
            themed = halloween_translation(singular, partial(super().gettext, locale=resolved_locale))
            if themed is not None:
                return themed
        text = super().gettext(singular, plural, n, resolved_locale)
        return decorate_translation(singular, text, self._theme.get())


i18n = CatalogI18n(path=Path(__file__).resolve().parents[2] / "locales", default_locale=DEFAULT_LOCALE.value)
