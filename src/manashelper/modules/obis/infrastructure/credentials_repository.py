from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.users.infrastructure.user import User


class ObisCredentialsRepository:
    """Own OBIS credential columns on the existing User row without changing its identity map."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def lock(self, user_id: int) -> None:
        await self._session.execute(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
