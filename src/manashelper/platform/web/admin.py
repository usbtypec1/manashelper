import re
from dataclasses import asdict

from aiohttp import web
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.profile import ProfileFilter
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.web.auth import authenticate

_PAGE_SIZE = 50


def parse_telegram_id(raw: str) -> int:
    if not re.fullmatch(r"-?[0-9]{1,19}", raw):
        raise ValueError("Invalid Telegram ID")
    cursor = int(raw)
    if not -(2**63) <= cursor < 2**63:
        raise ValueError("Invalid Telegram ID")
    return cursor


def require_admin(request: web.Request, settings: Settings) -> int:
    user_id = authenticate(request.headers.get("Authorization", ""), settings.telegram_bot_token)
    if user_id not in settings.admin_panel_user_ids:
        raise web.HTTPForbidden()
    return user_id


def user_cursor(request: web.Request) -> int | None:
    raw = request.query.get("after")
    try:
        return parse_telegram_id(raw) if raw is not None else None
    except ValueError as error:
        raise web.HTTPBadRequest() from error


def _profile_filter(request: web.Request) -> ProfileFilter:
    search = request.query.get("q", "").strip()
    status = request.query.get("status")
    if len(search) > 128 or status not in {None, "active", "stopped"}:
        raise web.HTTPBadRequest()
    try:
        locale, theme = request.query.get("locale"), request.query.get("theme")
        return ProfileFilter(
            search=search,
            locale=Locale(locale) if locale is not None else None,
            theme=Theme(theme) if theme is not None else None,
            bot_stopped=status == "stopped" if status is not None else None,
        )
    except ValueError as error:
        raise web.HTTPBadRequest() from error


def register_admin_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    async def list_users(request: web.Request) -> web.Response:
        require_admin(request, settings)
        after = user_cursor(request)
        filters = _profile_filter(request)
        async with container() as scope:
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
