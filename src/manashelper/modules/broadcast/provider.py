from dishka import Provider, Scope, provide

from manashelper.modules.broadcast.application.use_cases.send_broadcast import SendBroadcastUseCase


class BroadcastProvider(Provider):
    scope = Scope.REQUEST

    send_broadcast = provide(SendBroadcastUseCase)
