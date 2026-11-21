import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict

from aiohttp import web
from dishka import AsyncContainer
from pydantic import BaseModel, ConfigDict, StrictBool

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.profile import ProfileFilter
from manashelper.modules.users.application.queries import UsersQuery
from manashelper.modules.users.application.use_cases.set_user_blocked import SetUserBlockedUseCase
from manashelper.platform.web.auth import authenticate

_PAGE_SIZE = 50


def parse_telegram_id(raw: str) -> int:
    if not re.fullmatch(r"-?[0-9]{1,19}", raw):
        raise ValueError("Invalid Telegram ID")
    cursor = int(raw)
    if not -(2**63) <= cursor < 2**63:
        raise ValueError("Invalid Telegram ID")
    return cursor


@asynccontextmanager
async def admin_scope(
    request: web.Request, container: AsyncContainer, settings: Settings
) -> AsyncIterator[tuple[AsyncContainer, int]]:
    user_id = authenticate(request.headers.get("Authorization", ""), settings.telegram_bot_token)
    if user_id not in settings.admin_panel_user_ids:
        raise web.HTTPForbidden()
    async with container() as scope:
        if await (await scope.get(UsersQuery)).is_blocked(user_id):
            raise web.HTTPForbidden()
        yield scope, user_id


def user_cursor(request: web.Request) -> int | None:
    raw = request.query.get("after")
    try:
        return parse_telegram_id(raw) if raw is not None else None
    except ValueError as error:
        raise web.HTTPBadRequest() from error


def _profile_filter(request: web.Request) -> ProfileFilter:
    search = request.query.get("q", "").strip()
    status = request.query.get("status")
    if len(search) > 128 or status not in {None, "active", "stopped", "blocked"}:
        raise web.HTTPBadRequest()
    try:
        locale, theme = request.query.get("locale"), request.query.get("theme")
        return ProfileFilter(
            search=search,
            locale=Locale(locale) if locale is not None else None,
            theme=Theme(theme) if theme is not None else None,
            bot_stopped=status == "stopped" if status in {"active", "stopped"} else None,
            is_blocked=status == "blocked" if status is not None else None,
        )
    except ValueError as error:
        raise web.HTTPBadRequest() from error


class _BlockingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocked: StrictBool


def register_admin_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    async def list_users(request: web.Request) -> web.Response:
        async with admin_scope(request, container, settings) as (scope, _):
            after = user_cursor(request)
            filters = _profile_filter(request)
            query = await scope.get(UsersQuery)
            profiles = await query.list_profiles(after=after, limit=_PAGE_SIZE + 1, filters=filters)
        page = profiles[:_PAGE_SIZE]
        return web.json_response(
            {
                "users": [{**asdict(profile), "id": str(profile.id)} for profile in page],
                "next_cursor": str(page[-1].id) if len(profiles) > _PAGE_SIZE else None,
            }
        )

    app.router.add_get("/api/admin/users", list_users)

    async def set_blocked(request: web.Request) -> web.Response:
        async with admin_scope(request, container, settings) as (scope, actor_id):
            try:
                target_id = parse_telegram_id(request.match_info["id"])
                body = _BlockingInput.model_validate(await request.json())
            except ValueError as error:
                raise web.HTTPBadRequest() from error
            if body.blocked and target_id == actor_id:
                raise web.HTTPForbidden()
            action = await scope.get(SetUserBlockedUseCase)
            if not await action.execute(target_id, blocked=body.blocked):
                raise web.HTTPNotFound()
        return web.json_response({"is_blocked": body.blocked})

    app.router.add_put("/api/admin/users/{id}/blocked", set_blocked)
