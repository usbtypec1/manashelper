from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from functools import partial
from gettext import GNUTranslations, translation
from pathlib import Path
from types import MappingProxyType

from aiogram.utils.i18n import I18n

from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.localization.theme import Theme
from manashelper.platform.i18n.themes import decorate_translation, halloween_translation
from ui_flows.ports.texts import TextCatalog


class CatalogI18n(I18n):
    """Synchronous formatting against an explicitly bound immutable DB snapshot.

    Standalone file mode remains available for compatibility/import verification;
    the application's singleton uses database mode and never reads user .mo data.
    """

    _theme: ContextVar[Theme] = ContextVar("theme", default=Theme.BASIC)
    _catalog: ContextVar[TextCatalog | None] = ContextVar("text_catalog", default=None)
    _labels: ContextVar[Mapping[tuple[str, str], frozenset[str]]] = ContextVar(
        "text_labels", default=MappingProxyType({})
    )

    def __init__(
        self, *, path: str | Path, default_locale: str, domain: str = "messages", database: bool = False
    ) -> None:
        self._database = database
        self._admin: GNUTranslations | None = None
        super().__init__(path=path, default_locale=default_locale, domain=domain)

    @property
    def current_theme(self) -> Theme:
        return self._theme.get()

    @property
    def current_catalog(self) -> TextCatalog:
        snapshot = self._catalog.get()
        if snapshot is None:
            raise RuntimeError("Bind a published DB text catalog before formatting user messages")
        return snapshot

    @contextmanager
    def use_catalog(self, snapshot: TextCatalog) -> Generator[None]:
        token = self._catalog.set(snapshot)
        try:
            yield
        finally:
            self._catalog.reset(token)

    @contextmanager
    def use_labels(self, labels: Mapping[tuple[str, str], frozenset[str]]) -> Generator[None]:
        token = self._labels.set(labels)
        try:
            yield
        finally:
            self._labels.reset(token)

    def reply_labels(self, key: str) -> frozenset[str]:
        labels = set(self._labels.get().get((key, self.current_locale), ()))
        for theme in Theme:
            with self.use_theme(theme):
                labels.add(self.gettext(key))
        return frozenset(labels)

    @contextmanager
    def use_theme(self, theme: Theme) -> Generator[None]:
        token = self._theme.set(theme)
        try:
            yield
        finally:
            self._theme.reset(token)

    @contextmanager
    def context(self) -> Generator[I18n]:
        token = I18n.set_current(self)
        try:
            yield self
        finally:
            I18n.reset_current(token)

    def find_locales(self) -> dict[str, GNUTranslations]:
        if self._database:
            return {}  # The user-facing runtime does not open any .mo files.
        translations = super().find_locales()
        english = translations[Locale.EN.value]
        for locale, catalog in translations.items():
            if locale != Locale.EN.value:
                catalog.add_fallback(english)
        return translations

    def gettext(self, singular: str, plural: str | None = None, n: int = 1, locale: str | None = None) -> str:
        resolved_locale = locale if locale is not None else self.current_locale
        if self._database:
            if singular.startswith(("ui_flows.editor.", "ui_flows.web.")):
                if self._admin is None:
                    self._admin = translation(self.domain, localedir=self.path, languages=["en"])
                return self._admin.gettext(singular)
            return self.current_catalog.gettext(singular, resolved_locale, self.current_theme.value, n)
        if resolved_locale not in self.locales:
            resolved_locale = Locale.EN.value
        if self.current_theme == Theme.HALLOWEEN:
            themed = halloween_translation(singular, partial(super().gettext, locale=resolved_locale))
            if themed is not None:
                return themed
        text = super().gettext(singular, plural, n, resolved_locale)
        return decorate_translation(singular, text, self._theme.get())


i18n = CatalogI18n(
    path=Path(__file__).resolve().parents[2] / "locales", default_locale=DEFAULT_LOCALE.value, database=True
)
