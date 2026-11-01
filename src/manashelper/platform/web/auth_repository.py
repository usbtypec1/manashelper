from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.platform.web.orm import AdminLoginTicket, AdminWebSession


@dataclass(frozen=True, slots=True)
class AuthenticatedAdmin:
    user_id: int
    expires_at: datetime


class AdminAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def issue(self, digest: str, user_id: int, expires_at: datetime) -> None:
        self._session.add(AdminLoginTicket(digest=digest, user_id=user_id, expires_at=expires_at))
        await self._session.flush()

    async def consume(self, digest: str, now: datetime, admin_id: int) -> int | None:
        user_id: int | None = await self._session.scalar(
            delete(AdminLoginTicket)
            .where(
                AdminLoginTicket.digest == digest,
                AdminLoginTicket.expires_at > now,
                AdminLoginTicket.user_id == admin_id,
            )
            .returning(AdminLoginTicket.user_id)
        )
        return user_id

    async def create_session(self, digest: str, user_id: int, expires_at: datetime) -> None:
        self._session.add(AdminWebSession(digest=digest, user_id=user_id, expires_at=expires_at))
        await self._session.flush()

    async def session(self, digest: str, now: datetime, admin_id: int) -> AuthenticatedAdmin | None:
        row = await self._session.scalar(
            select(AdminWebSession).where(
                AdminWebSession.digest == digest,
                AdminWebSession.expires_at > now,
                AdminWebSession.user_id == admin_id,
            )
        )
        return None if row is None else AuthenticatedAdmin(row.user_id, row.expires_at)

    async def revoke(self, digest: str) -> None:
        await self._session.execute(delete(AdminWebSession).where(AdminWebSession.digest == digest))

    async def purge_expired(self, now: datetime) -> int:
        deleted = 0
        for model in (AdminLoginTicket, AdminWebSession):
            rows = await self._session.scalars(delete(model).where(model.expires_at <= now).returning(model.digest))
            deleted += len(rows.all())
        return deleted
