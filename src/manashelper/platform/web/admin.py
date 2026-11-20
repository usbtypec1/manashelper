import re

from aiohttp import web
from dishka import AsyncContainer

from manashelper.core.config import Settings
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.web.auth import authenticate

_PAGE_SIZE = 50


def _parse_cursor(raw: str | None) -> int | None:
    if raw is None:
        return None
    if not re.fullmatch(r"-?[0-9]{1,19}", raw):
        raise web.HTTPBadRequest()
    cursor = int(raw)
    if not -(2**63) <= cursor < 2**63:
        raise web.HTTPBadRequest()
    return cursor


def register_admin_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    async def list_users(request: web.Request) -> web.Response:
        user_id = authenticate(request.headers.get("Authorization", ""), settings.telegram_bot_token)
        if user_id not in settings.admin_panel_user_ids:
            raise web.HTTPForbidden()
        after = _parse_cursor(request.query.get("after"))
        async with container() as scope:
            query = await scope.get(UsersQuery)
            profiles = await query.list_profiles(after=after, limit=_PAGE_SIZE + 1)
        page = profiles[:_PAGE_SIZE]
        return web.json_response(
            {
                "users": [
                    {"id": str(profile.id), "full_name": profile.full_name, "username": profile.username}
                    for profile in page
                ],
                "next_cursor": str(page[-1].id) if len(profiles) > _PAGE_SIZE else None,
            }
        )

    app.router.add_get("/api/admin/users", list_users)
