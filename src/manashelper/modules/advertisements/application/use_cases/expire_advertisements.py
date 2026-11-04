from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.advertisements.application.expiry import PublicationRemover
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository


@dataclass(frozen=True, slots=True)
class ExpireAdvertisementsUseCase:
    repository: AdvertisementRepository
    publications: PublicationRemover

    async def execute(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        for advertisement in await self.repository.get_expired(now):
            message_ids = [message.message_id for message in advertisement.channel_messages]
            await self.publications.delete_publications(message_ids)
            await self.repository.delete(advertisement)
