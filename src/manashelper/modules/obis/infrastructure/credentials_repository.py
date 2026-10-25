from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User


class ObisCredentialsRepository:
    """Own OBIS credential columns on the existing User row without changing its identity map."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)
