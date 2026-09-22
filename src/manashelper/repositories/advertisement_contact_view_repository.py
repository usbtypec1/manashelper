import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import AdvertisementContactView


class AdvertisementContactViewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, advertisement_id: uuid.UUID, viewer_user_id: int) -> None:
        self._session.add(
            AdvertisementContactView(id=uuid.uuid4(), advertisement_id=advertisement_id, viewer_user_id=viewer_user_id)
        )
