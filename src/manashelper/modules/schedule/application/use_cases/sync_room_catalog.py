from dataclasses import dataclass

from manashelper.modules.schedule.application.lesson_items import room_key
from manashelper.modules.schedule.infrastructure.models.room import Room
from manashelper.modules.schedule.infrastructure.repositories.room import RoomRepository
from manashelper.modules.schedule.infrastructure.timetable_client import TimetableClient
from manashelper.modules.schedule.infrastructure.timetable_parser import parse_room_catalog


@dataclass(frozen=True, slots=True)
class SyncRoomCatalogUseCase:
    """Mirror the site's room list (names and capacities); a parse failure keeps the previous catalog."""

    timetable_client: TimetableClient
    room_repository: RoomRepository

    async def execute(self) -> int:
        scraped = {room.id: room for room in parse_room_catalog(await self.timetable_client.fetch_room_catalog_html())}
        existing = {room.id: room for room in await self.room_repository.get_all()}
        for room_id, room in existing.items():
            if room_id not in scraped:
                await self.room_repository.delete(room)
        for room_id, source in scraped.items():
            key = room_key(source.name)
            current = existing.get(room_id)
            if current is None:
                self.room_repository.add(Room(id=room_id, name=source.name, capacity=source.capacity, room_key=key))
            elif (current.name, current.capacity, current.room_key) != (source.name, source.capacity, key):
                current.name, current.capacity, current.room_key = source.name, source.capacity, key
        return len(scraped)
