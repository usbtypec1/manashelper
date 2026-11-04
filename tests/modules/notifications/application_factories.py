from types import SimpleNamespace

from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.application.use_cases.set_broadcast_mute import SetBroadcastMuteUseCase
from manashelper.modules.notifications.application.use_cases.toggle_notification_setting import (
    ToggleNotificationSettingUseCase,
)


def build_notification_settings_service(notification_settings_repository, users):
    query = GetNotificationSettingsUseCase(notification_settings_repository, users)
    return SimpleNamespace(
        get_settings=query.execute,
        toggle_setting=ToggleNotificationSettingUseCase(
            notification_settings_repository=notification_settings_repository, users=users
        ).execute,
        set_broadcast_mute=SetBroadcastMuteUseCase(
            notification_settings_repository=notification_settings_repository, users=users
        ).execute,
    )
