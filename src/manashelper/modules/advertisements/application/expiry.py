from datetime import UTC, datetime
from typing import Protocol

from manashelper.modules.advertisements.infrastructure.advertisement_repository import AdvertisementRepository


class PublicationRemover(Protocol):
    async def delete_publications(self, message_ids: list[int]) -> None: ...


class ExpireAdvertisements:
    def __init__(self, repository: AdvertisementRepository, publications: PublicationRemover) -> None:
        self._repository = repository
        self._publications = publications

    async def execute(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        for advertisement in await self._repository.get_expired(now):
            message_ids = [message.message_id for message in advertisement.channel_messages]
            await self._publications.delete_publications(message_ids)
            await self._repository.delete(advertisement)
