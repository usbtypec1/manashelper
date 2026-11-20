from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from aiohttp import web
from dishka import AsyncContainer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.broadcast.application.campaigns import (
    Audience,
    Campaign,
    CampaignConflictError,
    CampaignDraft,
    CampaignNotFoundError,
    MessageVariant,
)
from manashelper.modules.broadcast.application.queries import CampaignsQuery
from manashelper.modules.broadcast.application.use_cases.create_campaign import CreateCampaignUseCase
from manashelper.modules.broadcast.application.use_cases.retry_campaign import RetryCampaignUseCase
from manashelper.modules.broadcast.sender import broadcast_body_fits
from manashelper.platform.web.admin import parse_telegram_id, require_admin, user_cursor

_PAGE_SIZE = 25
_DELIVERY_PAGE_SIZE = 50


class _Variant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locale: Locale | None = None
    theme: Theme | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4096)]


class _CreateCampaign(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    audience: Audience
    user_ids: list[str] = Field(default_factory=list)
    variants: list[_Variant] = Field(min_length=1, max_length=(len(Locale) + 1) * (len(Theme) + 1))

    def draft(self) -> CampaignDraft:
        user_ids = frozenset(parse_telegram_id(user_id) for user_id in self.user_ids)
        if bool(user_ids) == (self.audience == Audience.ALL):
            raise ValueError("Invalid audience list")
        keys = {(variant.locale, variant.theme) for variant in self.variants}
        if len(keys) != len(self.variants) or not all(broadcast_body_fits(variant.text) for variant in self.variants):
            raise ValueError("Invalid message variants")
        variants = tuple(MessageVariant(variant.locale, variant.theme, variant.text) for variant in self.variants)
        return CampaignDraft(self.id, self.audience, user_ids, variants)


def _uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise web.HTTPBadRequest() from error


def _summary(campaign: Campaign, counts: dict[str, int]) -> dict[str, Any]:
    draft = campaign.draft
    return {
        "id": str(draft.id),
        "created_at": campaign.created_at.isoformat(),
        "audience": draft.audience,
        "preview": draft.variants[0].text[:160],
        "counts": counts,
    }


def register_admin_broadcast_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    async def list_campaigns(request: web.Request) -> web.Response:
        require_admin(request, settings)
        before = request.query.get("before")
        async with container() as scope:
            query = await scope.get(CampaignsQuery)
            try:
                campaigns = await query.list_campaigns(
                    before=_uuid(before) if before is not None else None, limit=_PAGE_SIZE + 1
                )
            except CampaignNotFoundError as error:
                raise web.HTTPBadRequest() from error
        return web.json_response(
            {
                "campaigns": [_summary(campaign, counts) for campaign, counts in campaigns[:_PAGE_SIZE]],
                "next_cursor": str(campaigns[_PAGE_SIZE - 1][0].draft.id) if len(campaigns) > _PAGE_SIZE else None,
            }
        )

    async def get_campaign(request: web.Request) -> web.Response:
        require_admin(request, settings)
        async with container() as scope:
            query = await scope.get(CampaignsQuery)
            try:
                campaign, counts = await query.get(_uuid(request.match_info["id"]))
            except CampaignNotFoundError as error:
                raise web.HTTPNotFound() from error
        return web.json_response(
            {
                **_summary(campaign, counts),
                "user_ids": [str(user_id) for user_id in sorted(campaign.draft.user_ids)],
                "variants": [asdict(variant) for variant in campaign.draft.variants],
            }
        )

    async def create_campaign(request: web.Request) -> web.Response:
        author_id = require_admin(request, settings)
        try:
            draft = _CreateCampaign.model_validate(await request.json()).draft()
        except ValueError as error:
            raise web.HTTPBadRequest() from error
        async with container() as scope:
            use_case = await scope.get(CreateCampaignUseCase)
            try:
                campaign = await use_case.execute(author_id, draft)
            except CampaignConflictError as error:
                raise web.HTTPConflict() from error
        return web.json_response({"id": str(campaign.draft.id)}, status=201)

    async def list_deliveries(request: web.Request) -> web.Response:
        require_admin(request, settings)
        campaign_id = _uuid(request.match_info["id"])
        after = user_cursor(request)
        async with container() as scope:
            query = await scope.get(CampaignsQuery)
            try:
                deliveries = await query.deliveries(campaign_id, after=after, limit=_DELIVERY_PAGE_SIZE + 1)
            except CampaignNotFoundError as error:
                raise web.HTTPNotFound() from error
        return web.json_response(
            {
                "deliveries": [
                    {**asdict(delivery), "user_id": str(delivery.user_id)}
                    for delivery in deliveries[:_DELIVERY_PAGE_SIZE]
                ],
                "next_cursor": str(deliveries[_DELIVERY_PAGE_SIZE - 1].user_id)
                if len(deliveries) > _DELIVERY_PAGE_SIZE
                else None,
            }
        )

    async def retry_campaign(request: web.Request) -> web.Response:
        require_admin(request, settings)
        async with container() as scope:
            use_case = await scope.get(RetryCampaignUseCase)
            try:
                count = await use_case.execute(_uuid(request.match_info["id"]))
            except CampaignNotFoundError as error:
                raise web.HTTPNotFound() from error
        return web.json_response({"retried": count})

    app.router.add_get("/api/admin/broadcasts", list_campaigns)
    app.router.add_post("/api/admin/broadcasts", create_campaign)
    app.router.add_get("/api/admin/broadcasts/{id}", get_campaign)
    app.router.add_get("/api/admin/broadcasts/{id}/deliveries", list_deliveries)
    app.router.add_post("/api/admin/broadcasts/{id}/retry", retry_campaign)
