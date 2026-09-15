from enum import StrEnum


class Locale(StrEnum):
    KY = "ky"
    RU = "ru"
    EN = "en"
    TR = "tr"


DEFAULT_LOCALE = Locale.RU

_LANGUAGE_CODE_PREFIX_TO_LOCALE = {
    "ky": Locale.KY,
    "ru": Locale.RU,
    "en": Locale.EN,
    "tr": Locale.TR,
}


def resolve_from_language_code(language_code: str | None) -> Locale:
    """Map a Telegram client IETF language tag (e.g. "en", "ru-RU") to a supported locale.

    Falls back to `DEFAULT_LOCALE` when there's no language code, or it doesn't match one of
    the supported locales.
    """
    if not language_code:
        return DEFAULT_LOCALE
    primary_subtag = language_code.split("-", 1)[0].lower()
    return _LANGUAGE_CODE_PREFIX_TO_LOCALE.get(primary_subtag, DEFAULT_LOCALE)
