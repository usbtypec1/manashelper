from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme


class Audience(StrEnum):
    ALL = "all"
    ALLOWLIST = "allowlist"
    BLOCKLIST = "blocklist"


@dataclass(frozen=True, slots=True)
class MessageVariant:
    locale: Locale | None
    theme: Theme | None
    text: str


@dataclass(frozen=True, slots=True)
class CampaignDraft:
    id: UUID
    audience: Audience
    user_ids: frozenset[int]
    variants: tuple[MessageVariant, ...]

    def includes(self, user_id: int) -> bool:
        match self.audience:
            case Audience.ALLOWLIST:
                return user_id in self.user_ids
            case Audience.BLOCKLIST:
                return user_id not in self.user_ids
            case Audience.ALL:
                return True

    def messages_by_preference(self) -> dict[tuple[Locale, Theme], str]:
        variants = {(variant.locale, variant.theme): variant.text for variant in self.variants}
        fallback = variants.get((None, None), self.variants[0].text)
        return {
            (locale, theme): variants.get((locale, theme))
            or variants.get((locale, None))
            or variants.get((None, theme))
            or fallback
            for locale in Locale
            for theme in Theme
        }


@dataclass(frozen=True, slots=True)
class Campaign:
    draft: CampaignDraft
    author_id: int
    created_at: datetime


class CampaignConflictError(ValueError):
    pass


class CampaignNotFoundError(LookupError):
    pass


class CampaignDelivery(Protocol):
    def enqueue(self, draft: CampaignDraft, recipients: list[tuple[int, Locale, Theme]]) -> None: ...
