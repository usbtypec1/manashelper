from dataclasses import asdict
from uuid import UUID

from sqlalchemy import literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.broadcast.application.campaigns import (
    Audience,
    Campaign,
    CampaignDraft,
    CampaignNotFoundError,
    MessageVariant,
)
from manashelper.modules.broadcast.infrastructure.models.campaign import BroadcastCampaign


def _campaign(row: BroadcastCampaign) -> Campaign:
    variants = tuple(
        MessageVariant(Locale(locale) if locale else None, Theme(theme) if theme else None, variant["text"] or "")
        for variant in row.variants
        for locale, theme in [(variant["locale"], variant["theme"])]
    )
    draft = CampaignDraft(row.id, Audience(row.audience), frozenset(row.user_ids), variants)
    return Campaign(draft, row.author_id, row.created_at)


class CampaignRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, campaign: Campaign) -> bool:
        draft = campaign.draft
        statement = (
            insert(BroadcastCampaign)
            .values(
                id=draft.id,
                author_id=campaign.author_id,
                created_at=campaign.created_at,
                audience=draft.audience,
                user_ids=sorted(draft.user_ids),
                variants=[asdict(variant) for variant in draft.variants],
            )
            .on_conflict_do_nothing(index_elements=[BroadcastCampaign.id])
            .returning(BroadcastCampaign.id)
        )
        return await self._session.scalar(statement) is not None

    async def get(self, campaign_id: UUID) -> Campaign:
        campaign = await self._session.get(BroadcastCampaign, campaign_id)
        if campaign is None:
            raise CampaignNotFoundError
        return _campaign(campaign)

    async def list(self, *, before: UUID | None, limit: int) -> list[Campaign]:
        statement = select(BroadcastCampaign).order_by(BroadcastCampaign.created_at.desc(), BroadcastCampaign.id.desc())
        if before is not None:
            cursor = await self.get(before)
            statement = statement.where(
                tuple_(BroadcastCampaign.created_at, BroadcastCampaign.id)
                < tuple_(literal(cursor.created_at), literal(before))
            )
        return [_campaign(row) for row in await self._session.scalars(statement.limit(limit))]
