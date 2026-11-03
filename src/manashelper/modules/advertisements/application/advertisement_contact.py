import uuid
from dataclasses import dataclass

from manashelper.modules.advertisements.application.advertisement import AdvertisementNotFoundError
from manashelper.modules.advertisements.domain.contact import ContactStatus
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.advertisements.infrastructure.repositories.advertisement_contact_view import (
    AdvertisementContactViewRepository,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class ContactReveal:
    advertisement_title: str
    contact: ContactStatus


class AdvertisementContactService:
    def __init__(
        self,
        advertisement_repository: AdvertisementRepository,
        advertisement_contact_view_repository: AdvertisementContactViewRepository,
        users: UsersQuery,
    ) -> None:
        self._advertisement_repository = advertisement_repository
        self._advertisement_contact_view_repository = advertisement_contact_view_repository
        self._users = users

    async def reveal_contact(self, advertisement_id: uuid.UUID, viewer_user_id: int) -> ContactReveal:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None or advertisement.status != AdvertisementStatus.PUBLISHED.value:
            raise AdvertisementNotFoundError(advertisement_id)

        self._advertisement_contact_view_repository.add(advertisement_id, viewer_user_id)
        contact = ContactStatus(
            username=await self._users.get_username(advertisement.user_id),
            phone_numbers=list(advertisement.phone_numbers),
        )
        return ContactReveal(advertisement_title=advertisement.title, contact=contact)
