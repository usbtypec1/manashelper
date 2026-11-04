from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.notifications.repository import NotificationSettingsRepository


@dataclass(frozen=True, slots=True)
class NotificationRecipientsQuery:
    """Public recipient selections returning user IDs without ORM objects."""

    settings: NotificationSettingsRepository

    async def for_broadcasts(self) -> list[int]:
        return await self.settings.get_broadcast_recipient_ids(datetime.now(UTC))

    async def allows_queued_delivery(self, user_id: int, category: str, now: datetime) -> bool:
        return await self.settings.allows_queued_delivery(user_id, category, now)

    async def for_schedule_changes(self, course_id: int) -> list[int]:
        return await self.settings.get_user_ids_tracking_course_with_schedule_changes_enabled(course_id)

    async def for_exam_grades(self) -> list[int]:
        return await self.settings.get_user_ids_with_exam_grades_enabled()

    async def for_lesson_skips(self) -> list[int]:
        return await self.settings.get_user_ids_with_lesson_skips_enabled()
