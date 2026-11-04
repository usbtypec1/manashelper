import re

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_dish_name(name: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", name).strip().lower()
