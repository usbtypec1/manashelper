import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import UserPhoneNumber


class UserPhoneNumberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> Sequence[UserPhoneNumber]:
        result = await self._session.execute(
            select(UserPhoneNumber).where(UserPhoneNumber.user_id == user_id).order_by(UserPhoneNumber.created_at)
        )
        return result.scalars().all()

    async def get_by_id(self, phone_number_id: uuid.UUID) -> UserPhoneNumber | None:
        return await self._session.get(UserPhoneNumber, phone_number_id)

    async def add_if_missing(self, user_id: int, phone_number: str) -> None:
        result = await self._session.execute(
            select(UserPhoneNumber).where(
                UserPhoneNumber.user_id == user_id, UserPhoneNumber.phone_number == phone_number
            )
        )
        if result.scalar_one_or_none() is not None:
            return
        self._session.add(UserPhoneNumber(id=uuid.uuid4(), user_id=user_id, phone_number=phone_number))

    async def delete(self, phone_number: UserPhoneNumber) -> None:
        await self._session.delete(phone_number)
