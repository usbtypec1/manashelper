_TURKISH_FOLD_MAP = str.maketrans(
    {
        "ş": "s",
        "Ş": "s",
        "ș": "s",
        "Ș": "s",
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
    }
)


def fold_turkish(text: str) -> str:
    """Fold Turkish diacritics to their plain Latin equivalents and lowercase the result.

    Translating before lowercasing avoids Python's special-cased ``"İ".casefold()`` -> ``"i̇"``
    (i + combining dot above) expansion, since the map already turns "İ" into a plain "i".
    """
    return text.translate(_TURKISH_FOLD_MAP).lower()
