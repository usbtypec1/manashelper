import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.modules.advertisements.domain.contact import (
    ContactStatus,
    InvalidPhoneNumberError,
    MissingContactError,
    is_valid_phone_number,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementMediaType, AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.models.advertisement import Advertisement
from manashelper.modules.advertisements.infrastructure.models.advertisement_channel_message import (
    AdvertisementChannelMessage,
)
from manashelper.modules.advertisements.infrastructure.models.advertisement_media import AdvertisementMedia
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


def _to_summaries(advertisements: Sequence[Advertisement]) -> list[AdvertisementSummary]:
    return [_to_summary(advertisement) for advertisement in advertisements]


class AdvertisementService:
    MAX_ADS_PER_HOUR = 5
    MAX_MEDIA_ITEMS = 10

    def __init__(self, advertisement_repository: AdvertisementRepository, users: UsersQuery) -> None:
        self._advertisement_repository = advertisement_repository
        self._users = users

    async def get_contact_status(self, user_id: int, phone_numbers: Sequence[str] = ()) -> ContactStatus:
        if not await self._users.exists(user_id):
            raise UserNotFoundError(user_id)
        return ContactStatus(username=await self._users.get_username(user_id), phone_numbers=list(phone_numbers))

    async def assert_can_post(self, user_id: int) -> None:
        since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
        if await self._advertisement_repository.count_created_since(user_id, since) >= self.MAX_ADS_PER_HOUR:
            raise TooManyAdvertisementsError(user_id)

    async def create_advertisement(
        self,
        user_id: int,
        title: str,
        description: str,
        price: int | None,
        expires_at: datetime | None,
        media_items: Sequence[AdvertisementMediaItem],
        *,
        phone_number: str | None = None,
    ) -> AdvertisementSummary:
        await self.assert_can_post(user_id)
        phone_number = phone_number.strip() if phone_number is not None else None
        if phone_number is not None and not is_valid_phone_number(phone_number):
            raise InvalidPhoneNumberError(phone_number)
        numbers = [phone_number] if phone_number is not None else []
        if not (await self.get_contact_status(user_id, numbers)).has_contact:
            raise MissingContactError("A phone number or Telegram username is required")

        advertisement = Advertisement(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            description=description,
            price=price,
            phone_numbers=numbers,
            status=AdvertisementStatus.PENDING.value,
            expires_at=expires_at,
        )
        advertisement.media = [
            AdvertisementMedia(id=uuid.uuid4(), file_id=item.file_id, media_type=item.media_type.value, position=index)
            for index, item in enumerate(media_items)
        ]
        self._advertisement_repository.add(advertisement)
        return _to_summary(advertisement)

    async def get_page_by_user_id(self, user_id: int, page: int) -> AdvertisementPage:
        advertisements, total = await self._advertisement_repository.get_page_by_user_id(user_id, page, PAGE_SIZE)
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        return AdvertisementPage(items=_to_summaries(advertisements), page=page, total_pages=total_pages)

    async def get_owned_by_id(self, advertisement_id: uuid.UUID, user_id: int) -> AdvertisementSummary:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        if advertisement.user_id != user_id:
            raise AdvertisementForbiddenError(advertisement_id, user_id)
        return _to_summary(advertisement)

    async def delete_owned(self, advertisement_id: uuid.UUID, user_id: int) -> AdvertisementDeletionResult:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        if advertisement.user_id != user_id:
            raise AdvertisementForbiddenError(advertisement_id, user_id)

        result = AdvertisementDeletionResult(
            status=AdvertisementStatus(advertisement.status),
            channel_message_ids=[cm.message_id for cm in advertisement.channel_messages],
        )
        await self._advertisement_repository.delete(advertisement)
        return result

    async def record_channel_messages(self, advertisement_id: uuid.UUID, message_ids: Sequence[int]) -> None:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None:
            raise AdvertisementNotFoundError(advertisement_id)
        advertisement.channel_messages = [
            AdvertisementChannelMessage(id=uuid.uuid4(), message_id=message_id) for message_id in message_ids
        ]
