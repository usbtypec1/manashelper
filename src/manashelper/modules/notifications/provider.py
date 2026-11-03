from dishka import Provider, Scope, provide

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import NotificationSettingsService
from manashelper.modules.notifications.ui_delegates import NotificationUiDelegates


class NotificationsProvider(Provider):
    scope = Scope.REQUEST

    recipients = provide(NotificationRecipientsQuery)
    repository = provide(NotificationSettingsRepository)
    settings = provide(NotificationSettingsService)
    ui_delegates = provide(NotificationUiDelegates)
