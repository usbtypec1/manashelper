import uuid

from manashelper.db.models.advertisement import Advertisement, AdvertisementStatus
from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.db.models.user import UserRole
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.advertisement import AdvertisementMediaItem, AdvertisementNotFoundError, AdvertisementSummary

MODERATOR_ROLES = [UserRole.MARKETPLACE_ADMIN.value, UserRole.SUPERADMIN.value]


class ModeratorForbiddenError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} is not a moderator")
        self.user_id = user_id


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
    def __init__(self, advertisement_repository: AdvertisementRepository, user_repository: UserRepository) -> None:
        self._advertisement_repository = advertisement_repository
        self._user_repository = user_repository

    async def is_moderator(self, user_id: int) -> bool:
        user = await self._user_repository.get_by_id(user_id)
        return user is not None and user.role in MODERATOR_ROLES

    async def get_moderator_ids(self) -> list[int]:
        return await self._user_repository.get_ids_with_roles(MODERATOR_ROLES)

    async def approve(self, advertisement_id: uuid.UUID, moderator_id: int) -> AdvertisementSummary:
        if not await self.is_moderator(moderator_id):
            raise ModeratorForbiddenError(moderator_id)
        advertisement = await self._get_pending(advertisement_id)
        advertisement.status = AdvertisementStatus.PUBLISHED.value
        advertisement.rejection_comment = None
        return _to_summary(advertisement)

    async def reject(self, advertisement_id: uuid.UUID, moderator_id: int, comment: str | None) -> AdvertisementSummary:
        if not await self.is_moderator(moderator_id):
            raise ModeratorForbiddenError(moderator_id)
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
