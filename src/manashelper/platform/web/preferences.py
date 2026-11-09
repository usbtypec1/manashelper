"""Authenticated Mini App adapters for the bot's settings and course use cases."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import partial
from typing import Any
from uuid import UUID

from aiohttp import web
from dishka import AsyncContainer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from manashelper.core.config import Settings
from manashelper.modules.eders.application.tracking import EdersSetting, EdersTrackingService
from manashelper.modules.eders.application.use_cases.toggle_eders_setting import ToggleEdersSettingUseCase
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuMeal,
    FoodMenuSettingsQuery,
)
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal import ToggleFoodMenuMealUseCase
from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.application.use_cases.set_broadcast_mute import SetBroadcastMuteUseCase
from manashelper.modules.notifications.application.use_cases.toggle_notification_setting import (
    ToggleNotificationSettingUseCase,
)
from manashelper.modules.notifications.settings import NotificationSetting
from manashelper.modules.schedule.application.course import CourseNotFoundError, CourseQuery
from manashelper.modules.schedule.application.department import DepartmentQuery
from manashelper.modules.schedule.application.faculty import FacultyQuery
from manashelper.modules.schedule.application.use_cases.toggle_tracked_course import ToggleTrackedCourseUseCase
from manashelper.modules.users.application.locale import LocaleQuery
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.web.auth import authenticate
from manashelper.platform.web.preferences_catalog import ui_strings


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NotificationInput(PreferenceInput):
    setting: NotificationSetting
    enabled: bool = Field(strict=True)


class FoodInput(PreferenceInput):
    weekday: int = Field(strict=True, ge=0, le=6)
    meal: FoodMenuMeal
    enabled: bool = Field(strict=True)


class EdersInput(PreferenceInput):
    setting: EdersSetting
    enabled: bool = Field(strict=True)


class BroadcastInput(PreferenceInput):
    muted: bool = Field(strict=True)


class CourseInput(PreferenceInput):
    tracked: bool = Field(strict=True)


async def _body[T: BaseModel](request: web.Request, model: type[T]) -> T:
    try:
        return model.model_validate(await request.json())
    except (ValueError, ValidationError) as error:
        raise web.HTTPBadRequest() from error


def _uuid(request: web.Request, key: str) -> UUID:
    try:
        return UUID(request.query.get(key, ""))
    except ValueError as error:
        raise web.HTTPBadRequest() from error


def _json(payload: dict[str, Any]) -> web.Response:
    return web.json_response(payload, dumps=partial(json.dumps, default=str))


async def _settings(scope: AsyncContainer, user_id: int, settings: Settings) -> dict[str, Any]:
    locale = await (await scope.get(LocaleQuery)).get_locale(user_id)
    theme = await (await scope.get(ThemeQuery)).get_theme(user_id)
    notifications = await (await scope.get(GetNotificationSettingsUseCase)).execute(user_id)
    food = await (await scope.get(FoodMenuSettingsQuery)).get_settings(user_id)
    eders = await (await scope.get(EdersTrackingService)).get_settings(user_id) if settings.eders_enabled else None
    courses = await (await scope.get(CourseQuery)).get_tracked_courses(user_id)
    with i18n.use_theme(theme):
        ui = ui_strings(locale.value)
    return {
        "locale": locale.value,
        "theme": theme.value,
        "ui": ui,
        "notifications": asdict(notifications),
        "food": [asdict(day) for day in food.days],
        "eders": asdict(eders) if eders is not None else None,
        "tracked_courses": [asdict(course) for course in courses],
    }


def register_preferences_routes(app: web.Application, container: AsyncContainer, settings: Settings) -> None:
    @asynccontextmanager
    async def authorized(request: web.Request) -> AsyncIterator[tuple[AsyncContainer, int]]:
        user_id = authenticate(request.headers.get("Authorization", ""), settings.telegram_bot_token)
        async with container() as scope:
            if not await (await scope.get(UsersQuery)).exists(user_id):
                raise web.HTTPForbidden()
            yield scope, user_id

    async def get_settings(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    async def notifications(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            body = await _body(request, NotificationInput)
            await (await scope.get(ToggleNotificationSettingUseCase)).execute(
                user_id, body.setting, enabled=body.enabled
            )
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    async def food(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            body = await _body(request, FoodInput)
            await (await scope.get(ToggleFoodMenuMealUseCase)).execute(
                user_id, body.weekday, body.meal, enabled=body.enabled
            )
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    async def eders(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            if not settings.eders_enabled:
                raise web.HTTPNotFound()
            body = await _body(request, EdersInput)
            await (await scope.get(ToggleEdersSettingUseCase)).execute(user_id, body.setting, enabled=body.enabled)
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    async def broadcast(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            body = await _body(request, BroadcastInput)
            await (await scope.get(SetBroadcastMuteUseCase)).execute(user_id, body.muted)
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    async def faculties(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, _):
            rows = await (await scope.get(FacultyQuery)).get_all_faculties()
        return _json({"faculties": [asdict(row) for row in rows]})

    async def departments(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, _):
            rows = await (await scope.get(DepartmentQuery)).get_departments_by_faculty(_uuid(request, "faculty_id"))
        return _json({"departments": [asdict(row) for row in rows]})

    async def courses(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            rows = await (await scope.get(CourseQuery)).get_courses_by_department(
                _uuid(request, "department_id"), user_id
            )
        return _json({"courses": [asdict(row) for row in rows]})

    async def track_course(request: web.Request) -> web.Response:
        async with authorized(request) as (scope, user_id):
            body = await _body(request, CourseInput)
            try:
                course_id = int(request.match_info["course_id"])
                if not 0 < course_id <= 2147483647:
                    raise ValueError
            except ValueError as error:
                raise web.HTTPBadRequest() from error
            try:
                await (await scope.get(ToggleTrackedCourseUseCase)).execute(course_id, user_id, tracked=body.tracked)
            except CourseNotFoundError as error:
                raise web.HTTPNotFound() from error
            payload = await _settings(scope, user_id, settings)
        return _json(payload)

    app.router.add_get("/api/settings", get_settings)
    app.router.add_put("/api/settings/notifications", notifications)
    app.router.add_put("/api/settings/food", food)
    app.router.add_put("/api/settings/eders", eders)
    app.router.add_put("/api/settings/broadcast", broadcast)
    app.router.add_get("/api/studies/faculties", faculties)
    app.router.add_get("/api/studies/departments", departments)
    app.router.add_get("/api/studies/courses", courses)
    app.router.add_put("/api/studies/courses/{course_id}", track_course)
