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


def resolve_from_language_code(language_code: str | None) -> Locale | None:
    """Map a Telegram client IETF language tag (e.g. "en", "ru-RU") to a supported locale.

    Returns None when the language can't be mapped to one of the supported locales, so the
    caller can fall back to asking the user to pick one explicitly.
    """
    if not language_code:
        return None
    primary_subtag = language_code.split("-", 1)[0].lower()
    return _LANGUAGE_CODE_PREFIX_TO_LOCALE.get(primary_subtag)
