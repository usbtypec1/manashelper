import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.types import Message
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from dishka import FromDishka, make_async_container
from dishka.integrations.aiogram import inject_router, setup_dishka
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.core.config import get_settings
from manashelper.core.provider import CoreProvider
from manashelper.localization.theme import Theme
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.food_menu.infrastructure.models.food_menu_notification_settings import (
    FoodMenuNotificationSettings,
)
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.provider import GamificationProvider
from manashelper.modules.notifications.application.use_cases.get_notification_settings import (
    GetNotificationSettingsUseCase,
)
from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.application.course import CourseQuery
from manashelper.modules.schedule.infrastructure.models.associations import user_courses
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.application.use_cases.set_user_theme import SetUserThemeUseCase
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.dispatcher import on_error
from manashelper.platform.telegram.outbox.provider import OutboxProvider
from manashelper.platform.telegram.provider import TelegramPlatformProvider
from manashelper.platform.telegram.webhook_jobs import cleanup_webhook_receipts_job
from manashelper.platform.telegram.webhook_models import ProcessedTelegramUpdate
from manashelper.platform.web.auth import authenticate
from manashelper.platform.web.server import create_web_app
from tests.platform.web.factories import SECRET, TOKEN, USER_ID, authorization


@pytest.mark.parametrize("case", ["missing", "scheme", "expired", "future", "duplicate"])
def test_bad_init_data_rejected(case):
    # Construct timestamps at execution time, not test collection: a full suite
    # can take long enough for a future timestamp to enter the allowed window.
    headers = {
        "missing": "",
        "scheme": "Bearer x",
        "expired": authorization(age=3601),
        "future": authorization(age=-60),
        "duplicate": authorization() + "&auth_date=0",
    }
    with pytest.raises(web.HTTPUnauthorized):
        authenticate(headers[case], TOKEN)


@asynccontextmanager
async def application(*, eders_enabled: bool | None = None):
    settings = get_settings().model_copy(
        update={"telegram_bot_token": TOKEN, "public_url": "https://example.com", "webhook_secret": SecretStr(SECRET)}
    )
    if eders_enabled is not None:
        settings.eders_password = SecretStr("fixture-eders-password") if eders_enabled else None
    container = make_async_container(
        CoreProvider(),
        TelegramPlatformProvider(),
        UsersProvider(),
        GamificationProvider(),
        OutboxProvider(),
        NotificationsProvider(),
        ObisProvider(),
        EdersProvider(),
        ScheduleProvider(),
        FoodMenuProvider(),
    )
    dispatcher = Dispatcher()
    calls = []

    @dispatcher.message()
    async def received(message: Message, activity: FromDishka[RecordActivityUseCase]):
        calls.append(message.text)
        await activity.execute(USER_ID, "published")
        if message.text == "fail":
            raise RuntimeError("Synthetic handler failure")
        if message.text == "slow":
            await asyncio.sleep(0.2)

    dispatcher.errors.register(on_error)
    setup_dishka(container, dispatcher)
    inject_router(dispatcher)
    async with Bot(TOKEN) as bot:
        async with container() as scope:
            session = await scope.get(AsyncSession)
            await clear_fixture_user(session)
            session.add(User(id=USER_ID, full_name="<script>Fixture</script>", locale="ru"))
            await (await scope.get(AchievementRepository)).set_enabled(USER_ID, True)
        try:
            async with TestClient(TestServer(create_web_app(bot, dispatcher, container, settings))) as client:
                yield client, container, calls
        finally:
            async with container() as scope:
                session = await scope.get(AsyncSession)
                await clear_fixture_user(session)
                await session.execute(
                    delete(ProcessedTelegramUpdate).where(ProcessedTelegramUpdate.update_id.between(992000, 992099))
                )
            await container.close()
            await dispatcher.storage.close()


async def clear_fixture_user(session):
    existing = await session.get(User, USER_ID)
    if existing is not None:
        assert existing.full_name == "<script>Fixture</script>"
    await session.execute(delete(user_courses).where(user_courses.c.user_id == USER_ID))
    await session.execute(delete(FoodMenuNotificationSettings).where(FoodMenuNotificationSettings.user_id == USER_ID))
    await session.execute(delete(NotificationSettings).where(NotificationSettings.user_id == USER_ID))
    await session.execute(delete(User).where(User.id == USER_ID))


@asynccontextmanager
async def course_catalog(container):
    faculty_id, department_id = uuid4(), uuid4()
    course_ids = [992001, 992002]
    async with container() as scope:
        session = await scope.get(AsyncSession)
        faculty = Faculty(id=faculty_id, name="Faculty <test>")
        department = Department(id=department_id, name="Department <test>", faculty=faculty)
        session.add_all(
            [Course(id=course_id, number=index, department=department) for index, course_id in enumerate(course_ids, 1)]
        )
    try:
        yield faculty_id, department_id, course_ids
    finally:
        async with container() as scope:
            session = await scope.get(AsyncSession)
            await session.execute(delete(user_courses).where(user_courses.c.course_id.in_(course_ids)))
            await session.execute(delete(Course).where(Course.id.in_(course_ids)))
            await session.execute(delete(Department).where(Department.id == department_id))
            await session.execute(delete(Faculty).where(Faculty.id == faculty_id))


async def test_preferences_are_available_without_achievement_access_and_keep_defaults():
    async with application(eders_enabled=True) as (client, container, _):
        async with container() as scope:
            await (await scope.get(AchievementRepository)).set_enabled(USER_ID, False)
        headers = {"Authorization": authorization()}
        assert (await client.get("/api/gamification/me", headers=headers)).status == 403
        response = await client.get("/api/settings", headers=headers)
        assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        data = await response.json()
        assert data["locale"] == "ru" and data["ui"]["title"] == "Настройки"
        assert all(value for key, value in data["notifications"].items() if key.endswith("_enabled"))
        assert len(data["food"]) == 7 and all(day["lunch_enabled"] and day["dinner_enabled"] for day in data["food"])
        assert all(data["eders"].values()) and data["tracked_courses"] == []
        assert "student_number" not in json.dumps(data) and "encrypted_password" not in json.dumps(data)


async def test_saved_bot_theme_reaches_both_miniapps_and_resets_without_leaking_context():
    async with application() as (client, container, _):
        headers = {"Authorization": authorization()}
        for selected in (Theme.PICKME, Theme.DEADINSIDE, Theme.BASIC):
            async with container() as scope:
                await (await scope.get(SetUserThemeUseCase)).execute(USER_ID, selected)
            with i18n.use_theme(Theme.HALLOWEEN):
                preferences = await (await client.get("/api/settings", headers=headers)).json()
                achievements = await (await client.get("/api/gamification/me", headers=headers)).json()
                updated = await (
                    await client.put(
                        "/api/settings/notifications",
                        headers=headers,
                        json={"setting": "exam_grades", "enabled": False},
                    )
                ).json()
                assert i18n.current_theme == Theme.HALLOWEEN
            assert preferences["theme"] == achievements["theme"] == updated["theme"] == selected.value
            assert preferences["ui"] == updated["ui"]
            with i18n.context(), i18n.use_locale("ru"), i18n.use_theme(selected):
                assert preferences["ui"]["title"] == i18n.gettext("miniapp.ui.title")
                assert achievements["ui"]["collection"] == i18n.gettext("gamification.ui.collection")
            assert all(
                all(icon not in card["description"] for icon in ("🎀", "🥀", "🖤"))
                for card in achievements["achievements"]
            )


async def test_preference_writes_set_values_idempotently_and_are_shared_with_native_settings():
    async with application(eders_enabled=True) as (client, container, _):
        headers = {"Authorization": authorization()}
        for _ in range(2):
            response = await client.put(
                "/api/settings/notifications", headers=headers, json={"setting": "exam_grades", "enabled": False}
            )
            assert response.status == 200
            data = await response.json()
            assert not data["notifications"]["exam_grades_enabled"]
            assert data["notifications"]["lesson_skips_enabled"]
        async with container() as scope:
            native = await (await scope.get(GetNotificationSettingsUseCase)).execute(USER_ID)
            assert not native.exam_grades_enabled and native.schedule_changes_enabled
        for _ in range(2):
            response = await client.put(
                "/api/settings/food", headers=headers, json={"weekday": 0, "meal": "lunch", "enabled": False}
            )
            assert response.status == 200
            food = (await response.json())["food"]
            assert not food[0]["lunch_enabled"] and food[0]["dinner_enabled"]
            assert all(day["lunch_enabled"] for day in food[1:])
            response = await client.put(
                "/api/settings/eders", headers=headers, json={"setting": "new_materials", "enabled": False}
            )
            assert response.status == 200 and not (await response.json())["eders"]["new_materials"]
        response = await client.put("/api/settings/broadcast", headers=headers, json={"muted": True})
        until = (await response.json())["notifications"]["broadcast_muted_until"]
        response = await client.put("/api/settings/broadcast", headers=headers, json={"muted": True})
        assert (await response.json())["notifications"]["broadcast_muted_until"] == until
        response = await client.put("/api/settings/broadcast", headers=headers, json={"muted": False})
        assert (await response.json())["notifications"]["broadcast_muted_until"] is None


async def test_course_catalog_concurrent_selection_retries_and_removal_share_bot_tracking():
    async with (
        application() as (client, container, _),
        course_catalog(container) as (faculty_id, department_id, course_ids),
    ):
        headers = {"Authorization": authorization()}
        faculties = await (await client.get("/api/studies/faculties", headers=headers)).json()
        assert {"id": str(faculty_id), "name": "Faculty <test>"} in faculties["faculties"]
        departments = await (
            await client.get(f"/api/studies/departments?faculty_id={faculty_id}", headers=headers)
        ).json()
        assert departments["departments"] == [{"id": str(department_id), "name": "Department <test>"}]
        responses = await asyncio.gather(
            *(
                client.put(f"/api/studies/courses/{course_id}", headers=headers, json={"tracked": True})
                for course_id in course_ids
            )
        )
        assert all(response.status == 200 for response in responses)
        response = await client.put(f"/api/studies/courses/{course_ids[0]}", headers=headers, json={"tracked": True})
        assert response.status == 200
        assert {course["id"] for course in (await response.json())["tracked_courses"]} == set(course_ids)
        async with container() as scope:
            native = await (await scope.get(CourseQuery)).get_courses_by_department(department_id, USER_ID)
            assert all(course.is_tracked for course in native)
            recipients = await (await scope.get(NotificationRecipientsQuery)).for_schedule_changes(course_ids[0])
            assert USER_ID in recipients
        response = await client.put(f"/api/studies/courses/{course_ids[0]}", headers=headers, json={"tracked": False})
        assert [course["id"] for course in (await response.json())["tracked_courses"]] == [course_ids[1]]
        courses = await (
            await client.get(f"/api/studies/courses?department_id={department_id}", headers=headers)
        ).json()
        assert [course["is_tracked"] for course in courses["courses"]] == [False, True]


@pytest.mark.parametrize(
    "path,body",
    [
        ("settings/notifications", {"setting": "exam_grades", "enabled": "false"}),
        ("settings/notifications", {"setting": "invalid", "enabled": False}),
        ("settings/notifications", {"setting": "exam_grades", "enabled": False, "user_id": 1}),
        ("settings/food", {"weekday": 7, "meal": "lunch", "enabled": False}),
        ("settings/food", {"weekday": True, "meal": "lunch", "enabled": False}),
        ("settings/eders", {"setting": "invalid", "enabled": False}),
        ("settings/broadcast", {"muted": 1}),
        ("studies/courses/invalid", {"tracked": True}),
    ],
)
async def test_preference_validation_rejects_invalid_or_cross_user_inputs_without_changing_values(path, body):
    async with application(eders_enabled=True) as (client, _, __):
        headers = {"Authorization": authorization()}
        before = await (await client.get("/api/settings", headers=headers)).json()
        response = await client.put(f"/api/{path}", headers=headers, json=body)
        assert response.status == 400 and response.headers["Cache-Control"] == "no-store"
        assert await (await client.get("/api/settings", headers=headers)).json() == before


async def test_preferences_authentication_disabled_eders_and_invalid_catalog_ids():
    async with application(eders_enabled=False) as (client, _, __):
        for path in ("settings", "studies/faculties", "studies/departments", "studies/courses"):
            assert (await client.get(f"/api/{path}")).status == 401
            assert (await client.get(f"/api/{path}", headers={"Authorization": authorization(992099)})).status == 403
        for path, body in (("settings/broadcast", {"muted": True}), ("studies/courses/1", {"tracked": True})):
            assert (await client.put(f"/api/{path}", json=body)).status == 401
        headers = {"Authorization": authorization()}
        data = await (await client.get("/api/settings", headers=headers)).json()
        assert data["eders"] is None
        assert (
            await client.put(
                "/api/settings/eders", headers=headers, json={"setting": "new_materials", "enabled": False}
            )
        ).status == 404
        assert (await client.get("/api/studies/departments?faculty_id=invalid", headers=headers)).status == 400
        assert (await client.get("/api/studies/courses", headers=headers)).status == 400
        assert (
            await client.put("/api/studies/courses/2147483647", headers=headers, json={"tracked": True})
        ).status == 404


def update(update_id, text="okay"):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "text": text,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False, "first_name": "Fixture"},
        },
    }


async def test_webhook_secret_failure_rollback_success_commit_and_replay():
    async with application() as (client, container, calls):
        assert (await client.post("/telegram/webhook", json=update(992010))).status == 401
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010, "fail"))).status == 500
        async with container() as scope:
            session = await scope.get(AsyncSession)
            assert await session.get(ProcessedTelegramUpdate, 992010) is None
            assert await session.scalar(select(User.id).where(User.id == USER_ID)) == USER_ID
            assert await (await scope.get(AchievementRepository)).get_awards(USER_ID) == {}
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010))).status == 200
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992010))).status == 200
        assert calls == ["fail", "okay"]
        response = await client.get("/api/gamification/me", headers={"Authorization": authorization()})
        assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        data = await response.json()
        assert data["score"] == 1 and data["locale"] == "ru"
        assert next(card for card in data["achievements"] if card["key"] == "seller")["earned_at"]
        assert "student_number" not in json.dumps(data)


async def test_webhook_receipts_are_cleaned_by_background_job_only():
    async with application() as (client, container, calls):
        now = datetime.now(UTC)
        async with container() as scope:
            session = await scope.get(AsyncSession)
            session.add_all(
                [
                    ProcessedTelegramUpdate(update_id=992020, processed_at=now - timedelta(days=3)),
                    ProcessedTelegramUpdate(update_id=992021, processed_at=now - timedelta(days=1)),
                ]
            )
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992022))).status == 200
        async with container() as scope:
            session = await scope.get(AsyncSession)
            assert await session.get(ProcessedTelegramUpdate, 992020) is not None
        await cleanup_webhook_receipts_job(container)
        async with container() as scope:
            session = await scope.get(AsyncSession)
            assert await session.get(ProcessedTelegramUpdate, 992020) is None
            assert await session.get(ProcessedTelegramUpdate, 992021) is not None
            assert await session.get(ProcessedTelegramUpdate, 992022) is not None


async def test_api_authorization_unknown_user_and_leaderboard_privacy():
    async with application() as (client, container, calls):
        assert (await client.get("/api/gamification/me")).status == 401
        assert (
            await client.get("/api/gamification/me", headers={"Authorization": authorization(992099)})
        ).status == 403
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        await client.post("/telegram/webhook", headers=headers, json=update(992011))
        response = await client.get("/api/gamification/leaderboard", headers={"Authorization": authorization()})
        data = await response.json()
        mine = next(entry for entry in data["entries"] if entry["is_self"])
        assert mine["full_name"] == "<script>Fixture</script>"
        assert set(mine) == {"full_name", "score", "rank", "is_self", "achievements"}
        assert [award["key"] for award in mine["achievements"]] == ["seller"]
        assert set(mine["achievements"][0]) == {"key", "name", "description", "earned_at"}
        assert response.headers["Cache-Control"] == "no-store"


async def test_miniapp_history_routes_serve_shell_but_assets_and_api_keep_their_handlers(monkeypatch, tmp_path):
    from manashelper.platform.web import server

    (tmp_path / "index.html").write_text("<html>Mini App shell</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('asset')")
    monkeypatch.setattr(server, "STATIC_DIR", tmp_path)
    async with application() as (client, _, __):
        for path in (
            "/app",
            "/app/",
            "/app/achievements",
            "/app/leaderboard",
            "/app/settings",
            "/app/courses",
            "/app/terms",
        ):
            response = await client.get(path)
            assert response.status == 200
            assert await response.text() == "<html>Mini App shell</html>"
            assert response.headers["Cache-Control"] == "no-cache"
        response = await client.get("/app/assets/app.js")
        assert response.status == 200 and await response.text() == "console.log('asset')"
        assert (await client.get("/app/assets/missing.js")).status == 404
        assert (await client.get("/api/settings")).status == 401
        assert (await client.get("/api/unknown")).status == 404


async def test_leaderboard_exposes_only_earned_awards_of_enabled_participants():
    async with application() as (client, container, _):
        other_id = 992098
        try:
            async with container() as scope:
                session = await scope.get(AsyncSession)
                session.add(User(id=other_id, full_name="Another participant", locale="tr", student_number="private"))
                await session.flush()
                repository = await scope.get(AchievementRepository)
                await repository.set_enabled(other_id, True)
                await repository.award(other_id, "champion", datetime.now(UTC))
            headers = {"Authorization": authorization()}
            response = await client.get("/api/gamification/leaderboard", headers=headers)
            entry = next(entry for entry in (await response.json())["entries"] if not entry["is_self"])
            assert entry["score"] == len(entry["achievements"]) == 1
            award = entry["achievements"][0]
            assert award["key"] == "champion" and award["earned_at"]
            with i18n.context(), i18n.use_locale("ru"):
                assert award["name"] == i18n.gettext("gamification.champion.name")
            assert set(award) == {"key", "name", "description", "earned_at"}
            assert set(entry) == {"full_name", "score", "rank", "is_self", "achievements"}
            async with container() as scope:
                await (await scope.get(AchievementRepository)).set_enabled(other_id, False)
            response = await client.get("/api/gamification/leaderboard", headers=headers)
            assert not any(entry["full_name"] == "Another participant" for entry in (await response.json())["entries"])
        finally:
            async with container() as scope:
                await (await scope.get(AsyncSession)).execute(delete(User).where(User.id == other_id))


async def test_disabled_user_cannot_access_either_api_even_with_valid_init_data():
    async with application() as (client, container, calls):
        async with container() as scope:
            await (await scope.get(AchievementRepository)).set_enabled(USER_ID, False)
        for path in ("me", "leaderboard"):
            response = await client.get(f"/api/gamification/{path}", headers={"Authorization": authorization()})
            assert response.status == 403
            assert response.headers["Cache-Control"] == "no-store"


async def test_fixture_authorization_is_independent_of_environment_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "telegram_bot_token", "different-ci-token")
    async with application() as (client, container, calls):
        response = await client.get("/api/gamification/me", headers={"Authorization": authorization()})
        assert response.status == 200


async def test_browser_fixture_authorization_is_independent_of_environment_token(monkeypatch):
    from tests.platform.web.preview import app

    monkeypatch.setattr(get_settings(), "telegram_bot_token", "different-ci-token")
    async with TestClient(TestServer(await app())) as client:
        fixture = await (await client.get("/_fixture/init-data")).json()
        response = await client.get("/api/gamification/me", headers={"Authorization": "tma " + fixture["initData"]})
        assert response.status == 200


async def test_concurrent_replay_is_not_acknowledged_before_processing():
    async with application() as (client, container, calls):
        headers = {"X-Telegram-Bot-Api-Secret-Token": SECRET}
        first = asyncio.create_task(client.post("/telegram/webhook", headers=headers, json=update(992012, "slow")))
        while not calls:
            await asyncio.sleep(0.01)
        second = await client.post("/telegram/webhook", headers=headers, json=update(992012, "slow"))
        assert second.status == 503
        assert (await first).status == 200
        assert (await client.post("/telegram/webhook", headers=headers, json=update(992012, "slow"))).status == 200
        assert calls == ["slow"]


@pytest.mark.skipif(not os.getenv("MANASHELPER_TELEGRAM_SIMULATION_URL"), reason="Optional local Telegram simulation")
async def test_real_aiogram_client_serializes_webhook_registration():
    import httpx

    url = os.environ["MANASHELPER_TELEGRAM_SIMULATION_URL"]
    async with httpx.AsyncClient() as http:
        await http.post(f"{url}/_reset")
        async with Bot(TOKEN, session=AiohttpSession(api=TelegramAPIServer.from_base(url))) as bot:
            assert await bot.set_webhook(
                "https://example.com/telegram/webhook",
                secret_token=SECRET,
                allowed_updates=["message", "callback_query"],
                max_connections=10,
                drop_pending_updates=False,
            )
        calls = (await http.get(f"{url}/_requests")).json()
        assert calls == [
            {
                "method": "setWebhook",
                "url": "https://example.com/telegram/webhook",
                "has_secret": True,
                "allowed_updates": '["message", "callback_query"]',
                "max_connections": 10,
            }
        ]
