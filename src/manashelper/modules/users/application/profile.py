from dataclasses import dataclass

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: int
    full_name: str
    username: str | None
    locale: Locale
    theme: Theme
    bot_stopped: bool


@dataclass(frozen=True, slots=True)
class ProfileFilter:
    search: str = ""
    locale: Locale | None = None
    theme: Theme | None = None
    bot_stopped: bool | None = None
