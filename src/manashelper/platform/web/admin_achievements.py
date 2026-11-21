from dataclasses import asdict
from typing import Annotated
from unicodedata import category

from aiohttp import web
from dishka import AsyncContainer
from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, field_validator

from manashelper.core.config import Settings
from manashelper.modules.gamification.application.catalog import ACHIEVEMENTS, AchievementDisplay
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.grant_achievement import GrantAchievementUseCase
from manashelper.modules.gamification.application.use_cases.set_achievement_display import SetAchievementDisplayUseCase
from manashelper.modules.gamification.presentation.catalog import achievement_strings
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.web.admin import admin_scope, parse_telegram_id


class _DisplayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    custom_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)] | None
    hidden: StrictBool

    @field_validator("custom_name")
    @classmethod
    def single_line(cls, value: str | None) -> str | None:
        if value is not None and any(category(char) in {"Cc", "Cs", "Zl", "Zp"} for char in value):
            raise ValueError("The name must be one line of text")
        return value


def register_admin_achievement_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    async def list_achievements(request: web.Request) -> web.Response:
        async with admin_scope(request, container, settings) as (scope, actor_id):
            query = await scope.get(GamificationQuery)
            overrides = await query.display_overrides()
            locale = await (await scope.get(LocaleQuery)).get_locale(actor_id)
        with i18n.context(), i18n.use_locale(locale.value):
            strings = achievement_strings()
        default = AchievementDisplay()
        return web.json_response(
            {
                "achievements": [
                    {
                        "key": item.key,
                        "emoji": item.emoji,
                        "default_name": strings[item.key][0],
                        **asdict(overrides.get(item.key, default)),
                    }
                    for item in ACHIEVEMENTS
                ]
            }
        )

    async def set_display(request: web.Request) -> web.Response:
        async with admin_scope(request, container, settings) as (scope, _):
            try:
                body = _DisplayInput.model_validate(await request.json())
            except ValueError as error:
                raise web.HTTPBadRequest() from error
            action = await scope.get(SetAchievementDisplayUseCase)
            display = AchievementDisplay(body.custom_name, body.hidden)
            if not await action.execute(request.match_info["key"], display):
                raise web.HTTPNotFound()
        return web.json_response(asdict(display))

    async def grant(request: web.Request) -> web.Response:
        async with admin_scope(request, container, settings) as (scope, actor_id):
            try:
                target_id = parse_telegram_id(request.match_info["id"])
                if target_id <= 0:
                    raise ValueError("A recipient must be a Telegram user")
            except ValueError as error:
                raise web.HTTPBadRequest() from error
            action = await scope.get(GrantAchievementUseCase)
            status = await action.execute(target_id, request.match_info["key"], granted_by=actor_id)
            if status == "missing":
                raise web.HTTPNotFound()
            if status == "unavailable":
                raise web.HTTPConflict()
        return web.json_response({"status": status})

    app.router.add_get("/api/admin/achievements", list_achievements)
    app.router.add_put("/api/admin/achievements/{key}", set_display)
    app.router.add_put("/api/admin/achievements/{key}/grants/{id}", grant)
