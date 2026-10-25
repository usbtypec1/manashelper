from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository


class NotificationRecipientsQuery:
    """Public recipient selections; notification persistence remains in legacy infrastructure."""

    def __init__(self, settings: NotificationSettingsRepository) -> None:
        self._settings = settings

    async def for_schedule_changes(self, course_id: int) -> list[int]:
        return await self._settings.get_user_ids_tracking_course_with_schedule_changes_enabled(course_id)
