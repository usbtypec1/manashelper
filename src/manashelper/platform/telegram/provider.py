from dishka import Provider, Scope, provide

from manashelper.platform.telegram.audit.repository import ActionLogRepository
from manashelper.platform.telegram.audit.service import ActionLogService
from manashelper.platform.telegram.deletions.repository import ScheduledMessageDeletionRepository
from manashelper.platform.telegram.deletions.service import MessageDeletionService
from manashelper.platform.telegram.middlewares.per_chat_ordering import ChatOrdering


class TelegramPlatformProvider(Provider):
    scope = Scope.REQUEST

    chat_ordering = provide(ChatOrdering, scope=Scope.APP)

    audit_repository = provide(ActionLogRepository)
    audit = provide(ActionLogService)
    deletion_repository = provide(ScheduledMessageDeletionRepository)
    deletions = provide(MessageDeletionService)
