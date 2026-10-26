from manashelper.modules.notifications.repository import NotificationSettingsRepository


class NotificationRecipientsQuery:
    """Public recipient selections returning user IDs without ORM objects."""

    def __init__(self, settings: NotificationSettingsRepository) -> None:
        self._settings = settings

    async def for_schedule_changes(self, course_id: int) -> list[int]:
        return await self._settings.get_user_ids_tracking_course_with_schedule_changes_enabled(course_id)

    async def for_exam_grades(self) -> list[int]:
        return await self._settings.get_user_ids_with_exam_grades_enabled()

    async def for_lesson_skips(self) -> list[int]:
        return await self._settings.get_user_ids_with_lesson_skips_enabled()
