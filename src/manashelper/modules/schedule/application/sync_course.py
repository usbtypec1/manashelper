from typing import Protocol

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.schedule.application.timetable_sync import LessonChange, TimetableSyncService


class ScheduleChangeSender(Protocol):
    async def send(self, user_id: int, changes: list[LessonChange]) -> None: ...


class SyncCourseTimetable:
    def __init__(self, sync: TimetableSyncService, recipients: NotificationRecipientsQuery) -> None:
        self._sync = sync
        self._recipients = recipients

    async def execute(self, course_id: int, sender: ScheduleChangeSender) -> None:
        changes = await self._sync.synchronize_course_timetable(course_id)
        if not changes:
            return
        user_ids = await self._recipients.for_schedule_changes(course_id)
        for user_id in user_ids:
            await sender.send(user_id, changes)
