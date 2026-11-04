from dataclasses import dataclass

from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import (
    NotificationSetting,
    NotificationSettingsSummary,
    get_or_create_notification_settings,
    to_summary,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class ToggleNotificationSettingUseCase:
    notification_settings_repository: NotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int, setting: NotificationSetting) -> NotificationSettingsSummary:
        settings = await get_or_create_notification_settings(self.notification_settings_repository, self.users, user_id)
        match setting:
            case NotificationSetting.SCHEDULE_CHANGES:
                settings.schedule_changes_enabled = not settings.schedule_changes_enabled
            case NotificationSetting.EXAM_GRADES:
                settings.exam_grades_enabled = not settings.exam_grades_enabled
            case NotificationSetting.LESSON_SKIPS:
                settings.lesson_skips_enabled = not settings.lesson_skips_enabled
        return to_summary(settings)
