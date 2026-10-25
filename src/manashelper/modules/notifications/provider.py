from dishka import Provider, Scope, provide

from manashelper.modules.notifications.queries import NotificationRecipientsQuery


class NotificationsProvider(Provider):
    scope = Scope.REQUEST

    recipients = provide(NotificationRecipientsQuery)
