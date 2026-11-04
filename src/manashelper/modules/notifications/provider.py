from dishka import Provider, Scope, provide

from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.application.use_cases.set_broadcast_mute import SetBroadcastMuteUseCase
from manashelper.modules.notifications.application.use_cases.toggle_notification_setting import (
    ToggleNotificationSettingUseCase,
)
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository


class NotificationsProvider(Provider):
    scope = Scope.REQUEST

    set_broadcast_mute_use_case = provide(SetBroadcastMuteUseCase)

    toggle_notification_setting_use_case = provide(ToggleNotificationSettingUseCase)

    recipients = provide(NotificationRecipientsQuery)
    repository = provide(NotificationSettingsRepository)
    settings = provide(GetNotificationSettingsUseCase)
