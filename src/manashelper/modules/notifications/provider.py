from dishka import Provider, Scope, provide

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.notifications.settings import NotificationSettingsService


class NotificationsProvider(Provider):
    scope = Scope.REQUEST

    recipients = provide(NotificationRecipientsQuery)
    repository = provide(NotificationSettingsRepository)
    settings = provide(NotificationSettingsService)
