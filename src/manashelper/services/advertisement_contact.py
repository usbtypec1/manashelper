import uuid
from dataclasses import dataclass

from manashelper.db.models.advertisement import AdvertisementStatus
from manashelper.repositories.advertisement_contact_view_repository import AdvertisementContactViewRepository
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.services.advertisement import AdvertisementNotFoundError
from manashelper.services.user_contact import ContactStatus, UserContactService


@dataclass(frozen=True, slots=True)
class ContactReveal:
    advertisement_title: str
    contact: ContactStatus


class AdvertisementContactService:
    def __init__(
        self,
        advertisement_repository: AdvertisementRepository,
        advertisement_contact_view_repository: AdvertisementContactViewRepository,
        user_contact_service: UserContactService,
    ) -> None:
        self._advertisement_repository = advertisement_repository
        self._advertisement_contact_view_repository = advertisement_contact_view_repository
        self._user_contact_service = user_contact_service

    async def reveal_contact(self, advertisement_id: uuid.UUID, viewer_user_id: int) -> ContactReveal:
        advertisement = await self._advertisement_repository.get_by_id(advertisement_id)
        if advertisement is None or advertisement.status != AdvertisementStatus.PUBLISHED.value:
            raise AdvertisementNotFoundError(advertisement_id)

        self._advertisement_contact_view_repository.add(advertisement_id, viewer_user_id)
        contact = await self._user_contact_service.get_contact_status(advertisement.user_id)
        return ContactReveal(advertisement_title=advertisement.title, contact=contact)
