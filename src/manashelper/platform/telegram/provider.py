from dishka import Provider, Scope, provide

from manashelper.platform.telegram.audit.repository import ActionLogRepository
from manashelper.platform.telegram.audit.service import ActionLogService
from manashelper.platform.telegram.deletions.repository import ScheduledMessageDeletionRepository
from manashelper.platform.telegram.deletions.service import MessageDeletionService


class TelegramPlatformProvider(Provider):
    scope = Scope.REQUEST

    audit_repository = provide(ActionLogRepository)
    audit = provide(ActionLogService)
    deletion_repository = provide(ScheduledMessageDeletionRepository)
    deletions = provide(MessageDeletionService)
