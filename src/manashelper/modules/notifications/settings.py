from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.users.queries import UsersQuery


class UserNotFoundError(Exception):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class NotificationSetting(StrEnum):
    SCHEDULE_CHANGES = "schedule_changes"
    EXAM_GRADES = "exam_grades"
    LESSON_SKIPS = "lesson_skips"


@dataclass(frozen=True, slots=True)
class NotificationSettingsSummary:
    schedule_changes_enabled: bool
    exam_grades_enabled: bool
    lesson_skips_enabled: bool
    broadcast_muted_until: datetime | None = None


def to_summary(settings: NotificationSettings) -> NotificationSettingsSummary:
    return NotificationSettingsSummary(
        schedule_changes_enabled=settings.schedule_changes_enabled,
        exam_grades_enabled=settings.exam_grades_enabled,
        lesson_skips_enabled=settings.lesson_skips_enabled,
        broadcast_muted_until=settings.broadcast_muted_until,
    )


async def get_or_create_notification_settings(
    notification_settings_repository: NotificationSettingsRepository, users: UsersQuery, user_id: int
) -> NotificationSettings:
    if not await users.exists(user_id):
        raise UserNotFoundError(user_id)
    return await notification_settings_repository.get_or_create(user_id)
