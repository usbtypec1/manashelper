from typing import Protocol

from manashelper.modules.schedule.application.timetable_sync import LessonChange


class ScheduleChangeSender(Protocol):
    async def send(self, user_id: int, changes: list[LessonChange]) -> None: ...
