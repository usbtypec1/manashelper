from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.users.infrastructure.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

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

    async def set_theme(self, user_id: int, theme: str) -> None:
        user = await self._session.get(User, user_id)
        if user is not None:
            user.theme = theme

    async def get_all_ids(self) -> list[int]:
        result = await self._session.execute(select(User.id))
        return list(result.scalars().all())

    async def get_active_ids(self) -> list[int]:
        result = await self._session.execute(select(User.id).where(User.bot_stopped.is_(False)))
        return list(result.scalars().all())

    async def set_bot_stopped(self, user_id: int, stopped: bool) -> None:
        user = await self.get_by_id(user_id)
        if user is not None:
            user.bot_stopped = stopped

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(User))
        return result.scalar_one()
