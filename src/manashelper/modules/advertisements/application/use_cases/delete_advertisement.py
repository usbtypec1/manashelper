import uuid
from dataclasses import dataclass

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementDeletionResult,
    AdvertisementForbiddenError,
    AdvertisementNotFoundError,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository


@dataclass(frozen=True, slots=True)
class DeleteAdvertisementUseCase:
    advertisement_repository: AdvertisementRepository

    async def execute(self, advertisement_id: uuid.UUID, user_id: int) -> AdvertisementDeletionResult:
        advertisement = await self.advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        if advertisement.user_id != user_id:
            raise AdvertisementForbiddenError(advertisement_id, user_id)
        result = AdvertisementDeletionResult(
            status=AdvertisementStatus(advertisement.status),
            channel_message_ids=[cm.message_id for cm in advertisement.channel_messages],
        )
        await self.advertisement_repository.delete(advertisement)
        return result
