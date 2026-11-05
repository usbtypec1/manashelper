import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementNotFoundError,
)
from manashelper.modules.advertisements.infrastructure.models.advertisement_channel_message import (
    AdvertisementChannelMessage,
)
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase


@dataclass(frozen=True, slots=True)
class RecordAdvertisementPublicationsUseCase:
    advertisement_repository: AdvertisementRepository
    activity: RecordActivityUseCase

    async def execute(self, advertisement_id: uuid.UUID, message_ids: Sequence[int]) -> None:
        advertisement = await self.advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        advertisement.channel_messages = [
            AdvertisementChannelMessage(id=uuid.uuid4(), message_id=message_id) for message_id in message_ids
        ]
        if message_ids:
            await self.activity.execute(advertisement.user_id, "published")
