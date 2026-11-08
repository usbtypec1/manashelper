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
        settings = await get_or_create_notification_settings(
            self.notification_settings_repository, self.users, user_id, lock=True
        )
        now = datetime.now(UTC)
        if not muted:
            settings.broadcast_muted_until = None
        elif settings.broadcast_muted_until is None or settings.broadcast_muted_until <= now:
            settings.broadcast_muted_until = now + timedelta(days=14)
        return to_summary(settings)
