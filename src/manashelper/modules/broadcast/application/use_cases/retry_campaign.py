from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from manashelper.modules.broadcast.infrastructure.repositories.campaign import CampaignRepository
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.platform.telegram.outbox.repository import OutboxRepository


@dataclass(frozen=True, slots=True)
class RetryCampaignUseCase:
    campaigns: CampaignRepository
    recipients: NotificationRecipientsQuery
    outbox: OutboxRepository

    async def execute(self, campaign_id: UUID) -> int:
        await self.campaigns.get(campaign_id)
        eligible = await self.recipients.for_broadcasts()
        return await self.outbox.retry_batch(campaign_id, eligible, datetime.now(UTC))
