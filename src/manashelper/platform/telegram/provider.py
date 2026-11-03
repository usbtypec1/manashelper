from dishka import Provider, Scope, provide

from manashelper.platform.telegram.audit.repository import ActionLogRepository
from manashelper.platform.telegram.audit.service import ActionLogService


class TelegramPlatformProvider(Provider):
    scope = Scope.REQUEST

    audit_repository = provide(ActionLogRepository)
    audit = provide(ActionLogService)
