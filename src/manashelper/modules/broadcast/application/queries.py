from dataclasses import dataclass
from uuid import UUID

from manashelper.modules.broadcast.application.campaigns import Campaign
from manashelper.modules.broadcast.infrastructure.repositories.campaign import CampaignRepository
from manashelper.platform.telegram.outbox.repository import BatchDelivery, OutboxRepository


@dataclass(frozen=True, slots=True)
class CampaignsQuery:
    campaigns: CampaignRepository
    outbox: OutboxRepository

    async def list_campaigns(self, *, before: UUID | None, limit: int) -> list[tuple[Campaign, dict[str, int]]]:
        campaigns = await self.campaigns.list(before=before, limit=limit)
        counts = await self.outbox.batch_counts([campaign.draft.id for campaign in campaigns])
        return [(campaign, counts.get(campaign.draft.id, {})) for campaign in campaigns]

    async def get(self, campaign_id: UUID) -> tuple[Campaign, dict[str, int]]:
        campaign = await self.campaigns.get(campaign_id)
        counts = await self.outbox.batch_counts([campaign_id])
        return campaign, counts.get(campaign_id, {})

    async def deliveries(self, campaign_id: UUID, *, after: int | None, limit: int) -> list[BatchDelivery]:
        await self.campaigns.get(campaign_id)
        return await self.outbox.batch_deliveries(campaign_id, after=after, limit=limit)
