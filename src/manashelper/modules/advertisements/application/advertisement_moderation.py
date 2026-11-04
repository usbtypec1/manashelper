import uuid

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementNotFoundError,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.models.advertisement import Advertisement
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository


class AdvertisementNotPendingError(Exception):
    def __init__(self, advertisement_id: uuid.UUID) -> None:
        super().__init__(f"Advertisement {advertisement_id} has already been reviewed")
        self.advertisement_id = advertisement_id


async def get_pending_advertisement(
    advertisement_repository: AdvertisementRepository, advertisement_id: uuid.UUID
) -> Advertisement:
    advertisement = await advertisement_repository.get_by_id(advertisement_id)
    if advertisement is None:
        raise AdvertisementNotFoundError(advertisement_id)
    if advertisement.status != AdvertisementStatus.PENDING.value:
        raise AdvertisementNotPendingError(advertisement_id)
    return advertisement
