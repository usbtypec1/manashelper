from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.platform.telegram.webhook_repository import WebhookReceiptRepository


class ConcurrentWebhookUpdateError(Exception):
    """A delivery of this update is already being processed; Telegram should retry."""


@dataclass(frozen=True, slots=True)
class WebhookReceiptService:
    repository: WebhookReceiptRepository

    async def begin(self, update_id: int) -> bool:
        if not await self.repository.try_lock(update_id):
            raise ConcurrentWebhookUpdateError()
        return not await self.repository.is_processed(update_id)

    async def complete(self, update_id: int) -> None:
        # Receipts share the handler's REQUEST transaction; neither commits alone.
        self.repository.add(update_id, datetime.now(UTC))

    async def cleanup(self) -> None:
        await self.repository.delete_before(datetime.now(UTC) - timedelta(days=2))
