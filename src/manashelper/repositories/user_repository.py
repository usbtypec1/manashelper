from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from manashelper.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_with_tracked_courses(self, user_id: int) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.tracked_courses)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: int, full_name: str, username: str | None) -> User:
        user = await self._session.get(User, user_id)
        if user is None:
            user = User(id=user_id, full_name=full_name, username=username)
            self._session.add(user)
        else:
            user.full_name = full_name
            user.username = username
        return user

    async def set_locale(self, user_id: int, locale: str) -> None:
        user = await self._session.get(User, user_id)
        if user is not None:
            user.locale = locale

    async def get_all_ids(self) -> list[int]:
        result = await self._session.execute(select(User.id))
        return list(result.scalars().all())
