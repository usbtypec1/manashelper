import uuid
from dataclasses import dataclass

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementSummary,
    to_summary,
)
from manashelper.modules.advertisements.application.advertisement_moderation import (
    get_pending_advertisement,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository


@dataclass(frozen=True, slots=True)
class ApproveAdvertisementUseCase:
    advertisement_repository: AdvertisementRepository

    async def execute(self, advertisement_id: uuid.UUID) -> AdvertisementSummary:
        advertisement = await get_pending_advertisement(self.advertisement_repository, advertisement_id)
        advertisement.status = AdvertisementStatus.PUBLISHED.value
        advertisement.rejection_comment = None
        return to_summary(advertisement)
