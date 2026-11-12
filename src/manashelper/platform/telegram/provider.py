from dishka import Provider, Scope, provide

from manashelper.platform.telegram.audit.repository import ActionLogRepository
from manashelper.platform.telegram.audit.service import ActionLogService
from manashelper.platform.telegram.webhook_repository import WebhookReceiptRepository
from manashelper.platform.telegram.webhook_service import WebhookReceiptService


class TelegramPlatformProvider(Provider):
    scope = Scope.REQUEST

    audit_repository = provide(ActionLogRepository)
    audit = provide(ActionLogService)
    webhook_repository = provide(WebhookReceiptRepository)
    webhook_receipts = provide(WebhookReceiptService)
