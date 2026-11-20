from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.broadcast.application.campaigns import (
    Campaign,
    CampaignConflictError,
    CampaignDelivery,
    CampaignDraft,
)
from manashelper.modules.broadcast.infrastructure.repositories.campaign import CampaignRepository
from manashelper.modules.notifications.queries import NotificationRecipientsQuery


@dataclass(frozen=True, slots=True)
class CreateCampaignUseCase:
    campaigns: CampaignRepository
    recipients: NotificationRecipientsQuery
    delivery: CampaignDelivery

    async def execute(self, author_id: int, draft: CampaignDraft) -> Campaign:
        campaign = Campaign(draft, author_id, datetime.now(UTC))
        if await self.campaigns.add(campaign):
            self.delivery.enqueue(draft, await self.recipients.broadcast_preferences())
            return campaign
        existing = await self.campaigns.get(draft.id)
        if existing.author_id != author_id or existing.draft != draft:
            raise CampaignConflictError
        return existing
