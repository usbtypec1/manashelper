import uuid

from manashelper.db.models.advertisement import Advertisement, AdvertisementStatus
from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.services.advertisement import AdvertisementMediaItem, AdvertisementNotFoundError, AdvertisementSummary


class AdvertisementNotPendingError(Exception):
    def __init__(self, advertisement_id: uuid.UUID) -> None:
        super().__init__(f"Advertisement {advertisement_id} has already been reviewed")
        self.advertisement_id = advertisement_id


def _to_summary(advertisement: Advertisement) -> AdvertisementSummary:
    return AdvertisementSummary(
        id=advertisement.id,
        user_id=advertisement.user_id,
        title=advertisement.title,
        description=advertisement.description,
        price=advertisement.price,
        status=AdvertisementStatus(advertisement.status),
        rejection_comment=advertisement.rejection_comment,
        expires_at=advertisement.expires_at,
        created_at=advertisement.created_at,
        media=[
            AdvertisementMediaItem(file_id=m.file_id, media_type=AdvertisementMediaType(m.media_type))
            for m in advertisement.media
        ],
    )


class AdvertisementModerationService:
    """Authorization for these actions isn't checked here: it's enforced by the router only
    accepting moderation callbacks/messages that originate from `Settings.moderation_chat_id` - see
    `bot/routers/advertisement_moderation.py`. There is no per-user moderator role anymore."""

    def __init__(self, advertisement_repository: AdvertisementRepository) -> None:
        self._advertisement_repository = advertisement_repository

    async def approve(self, advertisement_id: uuid.UUID) -> AdvertisementSummary:
        advertisement = await self._get_pending(advertisement_id)
        advertisement.status = AdvertisementStatus.PUBLISHED.value
        advertisement.rejection_comment = None
        return _to_summary(advertisement)

    async def reject(self, advertisement_id: uuid.UUID, comment: str | None) -> AdvertisementSummary:
        advertisement = await self._get_pending(advertisement_id)
        advertisement.status = AdvertisementStatus.REJECTED.value
        advertisement.rejection_comment = comment
        return _to_summary(advertisement)

    async def _get_pending(self, advertisement_id: uuid.UUID) -> Advertisement:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        if advertisement.status != AdvertisementStatus.PENDING.value:
            raise AdvertisementNotPendingError(advertisement_id)
        return advertisement
