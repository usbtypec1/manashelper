from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import (
    NotificationSettingsSummary,
    get_or_create_notification_settings,
    to_summary,
)
from manashelper.modules.users.queries import UsersQuery


@dataclass(frozen=True, slots=True)
class SetBroadcastMuteUseCase:
    notification_settings_repository: NotificationSettingsRepository
    users: UsersQuery

    async def execute(self, user_id: int, muted: bool) -> NotificationSettingsSummary:
        settings = await get_or_create_notification_settings(self.notification_settings_repository, self.users, user_id)
        settings.broadcast_muted_until = datetime.now(UTC) + timedelta(days=14) if muted else None
        return to_summary(settings)
