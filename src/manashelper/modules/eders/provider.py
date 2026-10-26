from dishka import Provider, Scope, provide

from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.polling import PollEdersUser
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.eders.infrastructure.repository import EdersRepository


class EdersProvider(Provider):
    client = provide(EdersClient, scope=Scope.APP)
    repository = provide(EdersRepository, scope=Scope.REQUEST)
    service = provide(EdersService, scope=Scope.REQUEST)
    tracking = provide(EdersTrackingService, scope=Scope.REQUEST)
    polling = provide(PollEdersUser, scope=Scope.REQUEST)
