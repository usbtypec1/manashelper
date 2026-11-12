from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.platform.telegram.webhook_models import ProcessedTelegramUpdate


@dataclass(frozen=True, slots=True)
class WebhookReceiptRepository:
    session: AsyncSession

    async def try_lock(self, update_id: int) -> bool:
        return bool(await self.session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": update_id}))

    async def is_processed(self, update_id: int) -> bool:
        return await self.session.get(ProcessedTelegramUpdate, update_id) is not None

    def add(self, update_id: int, processed_at: datetime) -> None:
        self.session.add(ProcessedTelegramUpdate(update_id=update_id, processed_at=processed_at))

    async def delete_before(self, cutoff: datetime) -> None:
        await self.session.execute(delete(ProcessedTelegramUpdate).where(ProcessedTelegramUpdate.processed_at < cutoff))
