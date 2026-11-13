"""Room and teacher views derived from the synchronized timetables of every course."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from manashelper.modules.schedule.application.course_level import parse_course_level
from manashelper.modules.schedule.application.lesson_items import (
    building_of,
    is_bookable_room,
    room_key,
    teacher_key,
)
from manashelper.modules.schedule.application.time_ranges import (
    parse_time_range_end_minutes,
    parse_time_range_start_minutes,
)
from manashelper.modules.schedule.application.timetable_entries import WORKDAYS, TimetableEntry
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_item import ItemRow, LessonItemRepository
from manashelper.modules.schedule.infrastructure.repositories.room import RoomRepository

MAX_SEARCH_RESULTS = 10
_NATURAL_SPLIT = re.compile(r"(\d+)")


@dataclass(frozen=True, slots=True)
class FreeRoom:
    key: str
    name: str
    building: str
    capacity: int | None
    free_until_minutes: int | None
    """Start of the room's next lesson that day; None when it stays free until the end of the day."""


@dataclass(frozen=True, slots=True)
class FreeRooms:
    weekday: int
    period: int
    periods: tuple[str, ...]
    rooms: tuple[FreeRoom, ...]

    @property
    def time_range(self) -> str:
        return self.periods[self.period]

    def buildings(self) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for room in self.rooms:
            counts[room.building] = counts.get(room.building, 0) + 1
        return sorted(counts.items())


@dataclass(frozen=True, slots=True)
class SearchMatch:
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class RoomInfo:
    key: str
    name: str
    capacity: int | None


def natural_sort_key(text: str) -> tuple[tuple[int, str], ...]:
    return tuple((1, f"{int(part):08d}") if part.isdigit() else (0, part) for part in _NATURAL_SPLIT.split(text))


def sort_periods(time_ranges: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(time_ranges), key=parse_time_range_start_minutes))


def current_period(periods: Sequence[str], now: datetime) -> tuple[int, int]:
    """(weekday, period index) in progress or about to start; after hours it moves to the next workday."""
    weekday, minutes = now.isoweekday(), now.hour * 60 + now.minute
    if weekday in WORKDAYS:
        for index, time_range in enumerate(periods):
            if minutes < parse_time_range_end_minutes(time_range):
                return weekday, index
    following = next((day for day in WORKDAYS if day > weekday), WORKDAYS[0])
    return following, 0


def to_entry(row: ItemRow) -> TimetableEntry:
    item, weekday, time_range, course_number, course_level, department_name = row
    return TimetableEntry(
        weekday=weekday,
        time_range=time_range,
        code=item.code,
        name=item.name,
        teacher=item.teacher,
        room=item.room,
        department_name=department_name,
        course_number=course_number,
        course_level=parse_course_level(course_level),
    )


@dataclass(frozen=True, slots=True)
class CampusQuery:
    lesson_repository: LessonRepository
    item_repository: LessonItemRepository
    room_repository: RoomRepository

    async def get_periods(self) -> tuple[str, ...]:
        return sort_periods(await self.lesson_repository.get_time_ranges())

    async def get_free_rooms(self, weekday: int, period: int, periods: Sequence[str] | None = None) -> FreeRooms:
        periods = tuple(periods) if periods is not None else await self.get_periods()
        if not periods:
            return FreeRooms(weekday=weekday, period=0, periods=(), rooms=())
        period = min(max(period, 0), len(periods) - 1)
        start = parse_time_range_start_minutes(periods[period])
        end = parse_time_range_end_minutes(periods[period])

        busy: dict[str, list[tuple[int, int]]] = {}
        for key, time_range in await self.item_repository.get_room_occupancy(weekday):
            interval = parse_time_range_start_minutes(time_range), parse_time_range_end_minutes(time_range)
            busy.setdefault(key, []).append(interval)

        catalog = await self._catalog()
        rooms: list[FreeRoom] = []
        for key, printed_name in await self.item_repository.get_room_names():
            if not is_bookable_room(printed_name):
                continue
            intervals = busy.get(key, [])
            if any(busy_start < end and busy_end > start for busy_start, busy_end in intervals):
                continue
            later = [busy_start for busy_start, _ in intervals if busy_start >= end]
            info = catalog.get(key)
            name = info.name if info is not None else printed_name
            rooms.append(
                FreeRoom(
                    key=key,
                    name=name,
                    building=building_of(name),
                    capacity=info.capacity if info is not None else None,
                    free_until_minutes=min(later) if later else None,
                )
            )
        rooms.sort(key=lambda room: (room.building, natural_sort_key(room.name)))
        return FreeRooms(weekday=weekday, period=period, periods=periods, rooms=tuple(rooms))

    async def search_rooms(self, query: str) -> list[SearchMatch]:
        key_query = room_key(query)
        if not key_query:
            return []
        catalog = await self._catalog()
        matches = await self.item_repository.search_rooms(key_query, MAX_SEARCH_RESULTS)
        return [
            SearchMatch(key=key, name=catalog[key].name if key in catalog else name)
            for key, name in matches
            if is_bookable_room(name)
        ]

    async def get_room(self, key: str) -> tuple[RoomInfo, list[TimetableEntry]] | None:
        rows = await self.item_repository.get_by_room_key(key)
        if not rows:
            return None
        catalog = await self._catalog()
        info = catalog.get(key) or RoomInfo(key=key, name=rows[0][0].room, capacity=None)
        return info, [to_entry(row) for row in rows]

    async def search_teachers(self, query: str) -> list[SearchMatch]:
        key_query = teacher_key(query)
        if not key_query:
            return []
        matches = await self.item_repository.search_teachers(key_query, MAX_SEARCH_RESULTS)
        return [SearchMatch(key=key, name=name) for key, name in matches]

    async def get_teacher(self, key: str) -> tuple[str, list[TimetableEntry]] | None:
        rows = await self.item_repository.get_by_teacher_key(key)
        if not rows:
            return None
        return rows[0][0].teacher, [to_entry(row) for row in rows]

    async def _catalog(self) -> dict[str, RoomInfo]:
        catalog: dict[str, RoomInfo] = {}
        for room in await self.room_repository.get_all():
            catalog.setdefault(room.room_key, RoomInfo(key=room.room_key, name=room.name, capacity=room.capacity))
        return catalog
