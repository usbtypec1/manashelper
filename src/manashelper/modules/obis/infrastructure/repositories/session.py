from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import StoredObisSession
from manashelper.modules.obis.infrastructure.models.session import ObisSession


class ObisSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> StoredObisSession | None:
        row = await self._session.get(ObisSession, user_id, populate_existing=True)
        return None if row is None else StoredObisSession(row.encrypted_cookies, row.created_at)

    async def save(self, user_id: int, session: StoredObisSession) -> None:
        await self._session.merge(
            ObisSession(user_id=user_id, encrypted_cookies=session.encrypted_cookies, created_at=session.created_at)
        )

    async def delete(self, user_id: int) -> StoredObisSession | None:
        query = (
            delete(ObisSession)
            .where(ObisSession.user_id == user_id)
            .returning(ObisSession.encrypted_cookies, ObisSession.created_at)
        )
        row = (await self._session.execute(query)).one_or_none()
        return None if row is None else StoredObisSession(row.encrypted_cookies, row.created_at)
