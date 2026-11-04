import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementMediaItem,
    AdvertisementSummary,
    assert_can_post_advertisement,
    get_advertisement_contact_status,
    to_summary,
)
from manashelper.modules.advertisements.domain.contact import (
    InvalidPhoneNumberError,
    MissingContactError,
    is_valid_phone_number,
)
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.models.advertisement import Advertisement
from manashelper.modules.advertisements.infrastructure.models.advertisement_media import AdvertisementMedia
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class CreateAdvertisementUseCase:
    advertisement_repository: AdvertisementRepository
    users: UsersQuery

    async def execute(
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
        await assert_can_post_advertisement(self.advertisement_repository, user_id)
        phone_number = phone_number.strip() if phone_number is not None else None
        if phone_number is not None and (not is_valid_phone_number(phone_number)):
            raise InvalidPhoneNumberError(phone_number)
        numbers = [phone_number] if phone_number is not None else []
        if not (await get_advertisement_contact_status(self.users, user_id, numbers)).has_contact:
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
        self.advertisement_repository.add(advertisement)
        return to_summary(advertisement)
