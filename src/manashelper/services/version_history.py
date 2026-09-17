import math
from dataclasses import dataclass
from datetime import date

from manashelper.db.models import BotVersion
from manashelper.repositories.bot_version_repository import BotVersionRepository

VERSIONS_PER_PAGE = 10


@dataclass(frozen=True, slots=True)
class VersionEntry:
    version: str
    released_at: date
    description: str


def _to_entry(bot_version: BotVersion) -> VersionEntry:
    return VersionEntry(
        version=bot_version.version, released_at=bot_version.released_at, description=bot_version.description
    )


class VersionHistoryService:
    def __init__(self, bot_version_repository: BotVersionRepository) -> None:
        self._bot_version_repository = bot_version_repository

    async def get_page(self, page: int) -> list[VersionEntry]:
        bot_versions = await self._bot_version_repository.get_page(page * VERSIONS_PER_PAGE, VERSIONS_PER_PAGE)
        return [_to_entry(bot_version) for bot_version in bot_versions]

    async def total_pages(self) -> int:
        total = await self._bot_version_repository.count()
        return max(1, math.ceil(total / VERSIONS_PER_PAGE))

    async def find_version(self, version: str) -> VersionEntry | None:
        bot_version = await self._bot_version_repository.get_by_version(version)
        return _to_entry(bot_version) if bot_version is not None else None
