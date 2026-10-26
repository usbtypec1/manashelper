from dishka import Provider, Scope, provide

from manashelper.modules.broadcast.service import SendBroadcast


class BroadcastProvider(Provider):
    scope = Scope.REQUEST

    send_broadcast = provide(SendBroadcast)
