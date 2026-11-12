from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.schedule.infrastructure.models.room import Room


class RoomRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Room]:
        result = await self._session.scalars(select(Room).order_by(Room.name))
        return result.all()

    def add(self, room: Room) -> None:
        self._session.add(room)

    async def delete(self, room: Room) -> None:
        await self._session.delete(room)
