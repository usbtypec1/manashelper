from dishka import Provider, Scope, provide

from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import OutboxService
from manashelper.platform.telegram.outbox.worker import OutboxWorker


class OutboxProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(OutboxRepository)
    service = provide(OutboxService)
    worker = provide(OutboxWorker)
