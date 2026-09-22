import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from manashelper.db.models import Advertisement


class AdvertisementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, advertisement: Advertisement) -> None:
        self._session.add(advertisement)

    async def get_by_id(self, advertisement_id: uuid.UUID) -> Advertisement | None:
        result = await self._session.execute(
            select(Advertisement)
            .options(selectinload(Advertisement.media), selectinload(Advertisement.channel_messages))
            .where(Advertisement.id == advertisement_id)
        )
        return result.scalar_one_or_none()

    async def get_page_by_user_id(self, user_id: int, page: int, page_size: int) -> tuple[Sequence[Advertisement], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(Advertisement).where(Advertisement.user_id == user_id)
        )
        result = await self._session.execute(
            select(Advertisement)
            .options(selectinload(Advertisement.media))
            .where(Advertisement.user_id == user_id)
            .order_by(Advertisement.created_at.desc())
            .limit(page_size)
            .offset(page * page_size)
        )
        return result.scalars().all(), total or 0

    async def count_created_since(self, user_id: int, since: datetime) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(Advertisement)
            .where(Advertisement.user_id == user_id, Advertisement.created_at >= since)
        )
        return total or 0

    async def get_expired(self, now: datetime) -> Sequence[Advertisement]:
        result = await self._session.execute(
            select(Advertisement)
            .options(selectinload(Advertisement.channel_messages))
            .where(Advertisement.expires_at.is_not(None), Advertisement.expires_at <= now)
        )
        return result.scalars().all()

    async def delete(self, advertisement: Advertisement) -> None:
        await self._session.delete(advertisement)
