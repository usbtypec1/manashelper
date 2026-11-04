from dataclasses import dataclass

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.schedule.application.sync_course import ScheduleChangeSender
from manashelper.modules.schedule.application.use_cases.sync_timetable import SyncTimetableUseCase


@dataclass(frozen=True, slots=True)
class SyncCourseTimetableUseCase:
    sync_timetable: SyncTimetableUseCase
    recipients: NotificationRecipientsQuery

    async def execute(self, course_id: int, sender: ScheduleChangeSender) -> None:
        changes = await self.sync_timetable.execute(course_id)
        if not changes:
            return
        user_ids = await self.recipients.for_schedule_changes(course_id)
        for user_id in user_ids:
            await sender.send(user_id, changes)
