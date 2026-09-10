from dataclasses import dataclass
from enum import StrEnum

from manashelper.db.models import NotificationSettings
from manashelper.repositories.notification_settings_repository import NotificationSettingsRepository
from manashelper.repositories.user_repository import UserRepository


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


def _to_summary(settings: NotificationSettings) -> NotificationSettingsSummary:
    return NotificationSettingsSummary(
        schedule_changes_enabled=settings.schedule_changes_enabled,
        exam_grades_enabled=settings.exam_grades_enabled,
        lesson_skips_enabled=settings.lesson_skips_enabled,
    )


class NotificationSettingsService:
    def __init__(
        self,
        notification_settings_repository: NotificationSettingsRepository,
        user_repository: UserRepository,
    ) -> None:
        self._notification_settings_repository = notification_settings_repository
        self._user_repository = user_repository

    async def get_settings(self, user_id: int) -> NotificationSettingsSummary:
        settings = await self._get_or_create(user_id)
        return _to_summary(settings)

    async def toggle_setting(self, user_id: int, setting: NotificationSetting) -> NotificationSettingsSummary:
        settings = await self._get_or_create(user_id)
        match setting:
            case NotificationSetting.SCHEDULE_CHANGES:
                settings.schedule_changes_enabled = not settings.schedule_changes_enabled
            case NotificationSetting.EXAM_GRADES:
                settings.exam_grades_enabled = not settings.exam_grades_enabled
            case NotificationSetting.LESSON_SKIPS:
                settings.lesson_skips_enabled = not settings.lesson_skips_enabled
        return _to_summary(settings)

    async def _get_or_create(self, user_id: int) -> NotificationSettings:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return await self._notification_settings_repository.get_or_create(user_id)
