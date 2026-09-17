from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import BotVersion


class BotVersionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_page(self, offset: int, limit: int) -> list[BotVersion]:
        result = await self._session.execute(
            select(BotVersion).order_by(BotVersion.sort_order.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(BotVersion))
        return result.scalar_one()

    async def get_by_version(self, version: str) -> BotVersion | None:
        result = await self._session.execute(select(BotVersion).where(BotVersion.version == version))
        return result.scalar_one_or_none()
