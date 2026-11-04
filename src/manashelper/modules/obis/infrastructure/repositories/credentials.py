from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.errors import UserNotFoundError
from manashelper.modules.users.infrastructure.models.user import User


class ObisCredentialsRepository:
    """Own OBIS credential columns on the existing User row without changing its identity map."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> StoredCredentials | None:
        user = await self._session.get(User, user_id)
        if user is None:
            return None
        return StoredCredentials(user.student_number, user.encrypted_password)

    async def save(self, user_id: int, credentials: StoredCredentials) -> None:
        user = await self._session.get(User, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        user.student_number = credentials.student_number
        user.encrypted_password = credentials.encrypted_password

    async def lock(self, user_id: int) -> None:
        await self._session.execute(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )
