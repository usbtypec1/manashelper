import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.modules.advertisements.domain.contact import (
    ContactStatus,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementMediaType, AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.models.advertisement import Advertisement
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.users.queries import UsersQuery

PAGE_SIZE = 10


class UserNotFoundError(Exception):
    pass


class AdvertisementNotFoundError(Exception):
    def __init__(self, advertisement_id: uuid.UUID) -> None:
        super().__init__(f"Advertisement {advertisement_id} not found")
        self.advertisement_id = advertisement_id


class AdvertisementForbiddenError(Exception):
    def __init__(self, advertisement_id: uuid.UUID, user_id: int) -> None:
        super().__init__(f"User {user_id} doesn't own advertisement {advertisement_id}")
        self.advertisement_id = advertisement_id
        self.user_id = user_id


class TooManyAdvertisementsError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} has posted too many advertisements in the last hour")
        self.user_id = user_id


@dataclass(frozen=True, slots=True)
class AdvertisementMediaItem:
    file_id: str
    media_type: AdvertisementMediaType


@dataclass(frozen=True, slots=True)
class AdvertisementSummary:
    id: uuid.UUID
    user_id: int
    title: str
    description: str
    price: int | None
    status: AdvertisementStatus
    rejection_comment: str | None
    expires_at: datetime | None
    created_at: datetime
    media: list[AdvertisementMediaItem]


@dataclass(frozen=True, slots=True)
class AdvertisementPage:
    items: list[AdvertisementSummary]
    page: int
    total_pages: int


@dataclass(frozen=True, slots=True)
class AdvertisementDeletionResult:
    status: AdvertisementStatus
    channel_message_ids: list[int]


def to_summary(advertisement: Advertisement) -> AdvertisementSummary:
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


def _to_summaries(advertisements: Sequence[Advertisement]) -> list[AdvertisementSummary]:
    return [to_summary(advertisement) for advertisement in advertisements]


@dataclass(frozen=True, slots=True)
class AdvertisementQuery:
    MAX_ADS_PER_HOUR = 5
    MAX_MEDIA_ITEMS = 10
    advertisement_repository: AdvertisementRepository
    users: UsersQuery

    async def get_contact_status(self, user_id: int, phone_numbers: Sequence[str] = ()) -> ContactStatus:
        return await get_advertisement_contact_status(self.users, user_id, phone_numbers)

    async def assert_can_post(self, user_id: int) -> None:
        return await assert_can_post_advertisement(self.advertisement_repository, user_id)

    async def get_page_by_user_id(self, user_id: int, page: int) -> AdvertisementPage:
        advertisements, total = await self.advertisement_repository.get_page_by_user_id(user_id, page, PAGE_SIZE)
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        return AdvertisementPage(items=_to_summaries(advertisements), page=page, total_pages=total_pages)

    async def get_owned_by_id(self, advertisement_id: uuid.UUID, user_id: int) -> AdvertisementSummary:
        advertisement = await self.advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        if advertisement.user_id != user_id:
            raise AdvertisementForbiddenError(advertisement_id, user_id)
        return to_summary(advertisement)


async def get_advertisement_contact_status(
    users: UsersQuery, user_id: int, phone_numbers: Sequence[str] = ()
) -> ContactStatus:
    if not await users.exists(user_id):
        raise UserNotFoundError(user_id)
    return ContactStatus(username=await users.get_username(user_id), phone_numbers=list(phone_numbers))


async def assert_can_post_advertisement(advertisement_repository: AdvertisementRepository, user_id: int) -> None:
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    if await advertisement_repository.count_created_since(user_id, since) >= AdvertisementQuery.MAX_ADS_PER_HOUR:
        raise TooManyAdvertisementsError(user_id)
