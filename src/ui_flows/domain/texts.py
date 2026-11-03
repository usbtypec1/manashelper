"""Immutable user-text contracts and deterministic, transport-independent lookup."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Annotated, Literal, cast

from pydantic import ConfigDict, Field, field_validator

from ui_flows.domain.schema import ContractModel, LocaleCode

TextTheme = Literal["basic", "halloween"]
PluralForm = Literal["one", "few", "many", "other"]


class TextVariant(ContractModel):
    model_config = ConfigDict(frozen=True)

    locale: LocaleCode
    theme: TextTheme
    form: PluralForm
    text: Annotated[str, Field(min_length=1, max_length=4096)]


class TextEntry(ContractModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(min_length=1, max_length=120)]
    owner: Annotated[str, Field(min_length=1, max_length=120)]
    parameters: tuple[str, ...] = ()
    content_type: Literal["plain", "html", "label"]
    plural_key: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    variants: tuple[TextVariant, ...]

    @field_validator("parameters", "variants", mode="before")
    @classmethod
    def immutable_sequences(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


class TextDocument(ContractModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    entries: tuple[TextEntry, ...]

    @field_validator("entries", mode="before")
    @classmethod
    def immutable_entries(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


def plural_form(locale: str, n: int) -> PluralForm:
    """Use the supported catalogs' fixed integer rules, never database expressions."""
    if type(n) is not int:
        raise ValueError("Plural quantity must be an integer")
    if locale == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
            return "few"
        return "many"
    if locale in {"tr", "zh"}:
        return "other"
    return "one" if n == 1 else "other"


def resolve_inline(
    translations: Mapping[LocaleCode, str],
    themes: Mapping[Literal["halloween"], Mapping[LocaleCode, str]],
    locale: str,
    theme: str,
) -> str:
    """Preserve the version-one InlineText theme and locale fallback order."""
    themed = themes.get("halloween", {}) if theme == "halloween" else {}
    locale_key = cast(LocaleCode, locale)
    return themed.get(locale_key) or translations.get(locale_key) or themed.get("en") or translations["en"]


@dataclass(frozen=True, slots=True)
class TextSnapshot:
    release_id: int
    document: TextDocument
    _entries: Mapping[str, TextEntry] = field(init=False, repr=False, compare=False)
    _variants: Mapping[tuple[str, str, str, str], str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        entries = {}
        variants = {}
        for entry in self.document.entries:
            entries[entry.key] = entry
            if entry.plural_key is not None:
                entries[entry.plural_key] = entry
            for variant in entry.variants:
                variants[entry.key, variant.locale, variant.theme, variant.form] = variant.text
        object.__setattr__(self, "_entries", MappingProxyType(entries))
        object.__setattr__(self, "_variants", MappingProxyType(variants))

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(self._entries)

    def entry(self, key: str) -> TextEntry:
        return self._entries[key]

    def gettext(self, key: str, locale: str = "en", theme: str = "basic", n: int = 1) -> str:
        entry = self.entry(key)
        if locale not in {"en", "ru", "ky", "tr", "zh"}:
            locale = "en"
        if theme not in {"basic", "halloween"}:
            theme = "basic"
        for candidate_locale, candidate_theme in ((locale, theme), (locale, "basic"), ("en", theme), ("en", "basic")):
            form = plural_form(candidate_locale, n) if entry.plural_key is not None else "other"
            value = self._variants.get((entry.key, candidate_locale, candidate_theme, form))
            if value is not None:
                return value
        raise KeyError(key)
