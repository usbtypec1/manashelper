from dataclasses import dataclass

from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import (
    NotificationSettingsSummary,
    get_or_create_notification_settings,
    to_summary,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class GetNotificationSettingsUseCase:
    notification_settings_repository: NotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int) -> NotificationSettingsSummary:
        settings = await get_or_create_notification_settings(self.notification_settings_repository, self.users, user_id)
        return to_summary(settings)
