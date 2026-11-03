import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select, update

from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.ui_flows.demo import demo_document
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession
from manashelper.modules.ui_flows.presentation.openapi import build_openapi
from manashelper.platform.web.auth import COOKIE_NAME, token_digest
from manashelper.platform.web.keys import SETTINGS_KEY
from manashelper.platform.web.orm import AdminLoginTicket, AdminWebSession
from tests.modules.ui_flows.admin_factory import aiohttp_client
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser

BASE = "/admin/api/v1"


async def publish_demo(api):
    document = demo_document().model_dump(mode="json")
    assert (await api.client.post(BASE + "/flows", json={"document": document})).status_code == 201
    response = await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 0})
    assert response.status_code == 200, response.text
    return document


async def test_one_use_ticket_cookie_session_and_logout(admin_api):
    api = admin_api
    assert (await api.client.get(BASE + "/flows")).status_code == 401
    ticket = await api.ticket()
    response = await api.client.post(
        BASE + "/auth/exchange", json={"ticket": ticket}, headers={"Origin": "https://wrong.test"}
    )
    assert response.status_code == 403
    response = await api.client.post(BASE + "/auth/exchange", json={"ticket": ticket})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie and "path=/admin" in cookie
    assert ticket not in response.text
    assert (await api.client.post(BASE + "/auth/exchange", json={"ticket": ticket})).status_code == 401
    current = await api.client.get(BASE + "/auth/session")
    assert current.status_code == 200 and current.json()["user_id"] == api.user_id
    assert (await api.client.post(BASE + "/auth/logout")).status_code == 403
    api.client.headers["X-CSRF-Token"] = current.json()["csrf_token"]
    logout = await api.client.post(BASE + "/auth/logout")
    assert logout.status_code == 204 and logout.content == b""
    assert "Content-Type" not in logout.headers
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401


async def test_ticket_exchange_is_atomic_under_concurrency(admin_api):
    api = admin_api
    ticket = await api.ticket()

    async def exchange():
        async with httpx.AsyncClient(
            base_url=api.client.base_url,
            verify=False,
            headers={"Origin": "https://admin.test"},
        ) as client:
            return await client.post(BASE + "/auth/exchange", json={"ticket": ticket})

    responses = await asyncio.wait_for(asyncio.gather(exchange(), exchange()), 5)
    assert sorted(response.status_code for response in responses) == [200, 401]
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(AdminWebSession)) == 1
        assert await session.get(AdminLoginTicket, token_digest(ticket)) is None


async def test_expiry_and_secret_redaction(admin_api):
    api = admin_api
    ticket = await api.ticket()
    async with api.pool.begin() as session:
        await session.execute(update(AdminLoginTicket).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert (await api.client.post(BASE + "/auth/exchange", json={"ticket": ticket})).status_code == 401
    raw = "private-ticket-value-that-must-never-be-echoed"
    response = await api.client.post(BASE + "/auth/exchange", json={"ticket": raw, "extra": raw})
    assert response.status_code == 422 and raw not in response.text
    await api.login()
    async with api.pool.begin() as session:
        row = await session.scalar(select(AdminWebSession))
        assert row.digest != api.client.cookies[COOKIE_NAME]
        await session.execute(update(AdminWebSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert (await api.client.get(BASE + "/auth/session")).status_code == 401


async def test_commit_failure_returns_no_cookie_and_preserves_ticket(admin_api):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from manashelper.platform.web.application import create_admin_app as create_app
    from tests.modules.ui_flows.admin_factory import admin_container, aiohttp_client

    api = admin_api
    ticket = await api.ticket()

    class FailSessionCommit(AsyncSession):
        async def commit(self):
            if await self.scalar(select(AdminWebSession)) is not None:
                raise RuntimeError("synthetic commit failure")
            await super().commit()

    pool = async_sessionmaker(api.pool.kw["bind"], class_=FailSessionCommit, expire_on_commit=False)
    async with admin_container(pool) as container:
        app = create_app(api.app[SETTINGS_KEY], container)
        async with aiohttp_client(app) as client:
            response = await client.post(BASE + "/auth/exchange", json={"ticket": ticket})
            assert response.status_code == 500 and "set-cookie" not in response.headers
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(AdminWebSession)) == 0
        assert await session.get(AdminLoginTicket, token_digest(ticket)) is not None
    assert (await api.client.post(BASE + "/auth/exchange", json={"ticket": ticket})).status_code == 200


async def test_drafts_publication_conflicts_rollback_and_contract(admin_api):
    api = admin_api
    await api.login()
    document = await publish_demo(api)
    document["nodes"][1]["text"] = [{"kind": "inline", "translations": {"en": "Changed menu"}}]
    saved = await api.client.put(
        BASE + "/flows/ui_flow_demo/draft", json={"document": document, "expected_revision": 0}
    )
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    assert (
        await api.client.put(BASE + "/flows/ui_flow_demo/draft", json={"document": document, "expected_revision": 0})
    ).status_code == 409
    assert (await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 1})).json()[
        "version"
    ] == 2
    activated = await api.client.post(
        BASE + "/flows/ui_flow_demo/activate", json={"version": 1, "expected_published_version": 2}
    )
    assert activated.status_code == 200 and activated.json()["published_version"] == 1
    assert (await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 1})).json()[
        "version"
    ] == 2
    assert (await api.client.get(BASE + "/flows/ui_flow_demo")).json()["published_version"] == 1
    versions = (await api.client.get(BASE + "/flows/ui_flow_demo/versions")).json()["items"]
    assert [item["version"] for item in versions] == [2, 1]
    assert (await api.client.get(BASE + "/flows/missing")).status_code == 404
    contract_paths = {
        (BASE + path, method.upper()) for path, methods in build_openapi()["paths"].items() for method in methods
    }
    actual_paths = {
        (route.resource.canonical, route.method)
        for route in api.app.router.routes()
        if (route.name or "").startswith("admin.") and route.method != "HEAD"
    }
    assert actual_paths == contract_paths
    assert {
        route.name.removeprefix("admin.")
        for route in api.app.router.routes()
        if (route.name or "").startswith("admin.")
    } == {operation["operationId"] for methods in build_openapi()["paths"].values() for operation in methods.values()}


async def test_invalid_screens_and_ids_cannot_be_published(admin_api):
    api = admin_api
    await api.login()
    document = demo_document().model_dump(mode="json")
    document["nodes"][1]["text"] = [{"kind": "inline", "translations": {"en": "<script>bad</script>"}}]
    assert (await api.client.post(BASE + "/flows", json={"document": document})).status_code == 201
    validation = await api.client.post(BASE + "/flows/ui_flow_demo/validate", json={"document": document})
    assert validation.status_code == 200 and validation.json()["issues"][0]["code"] == "invalid_screen"
    assert (
        await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 0})
    ).status_code == 422
    assert (await api.client.get(BASE + "/flows/ui_flow_demo")).json()["published_version"] is None
    assert (
        await api.client.put(BASE + "/flows/wrong/draft", json={"document": document, "expected_revision": 0})
    ).status_code == 422


async def test_api_publication_reaches_existing_runtime_container_without_restart(admin_api):
    api = admin_api
    await api.login()
    document = await publish_demo(api)
    user = RuntimeUser(api.user_id, api.user_id)
    async with api.container() as request:
        first = await (await request.get(DialogService)).start("ui_flow_demo", user, 7100)
    document["nodes"][1]["text"] = [{"kind": "inline", "translations": {"en": "Published through API"}}]
    saved = await api.client.put(
        BASE + "/flows/ui_flow_demo/draft", json={"document": document, "expected_revision": 0}
    )
    assert saved.status_code == 200
    assert (
        await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 1})
    ).status_code == 200
    async with api.container() as request:
        dialogs = await request.get(DialogService)
        assert (await dialogs.active(user)).flow_version == first.state.flow_version == 1
        await dialogs.cancel_active(user, 7101)
        second = await dialogs.start("ui_flow_demo", user, 7102)
        assert second.state.flow_version == 2
        assert second.node.text[0].translations["en"] == "Published through API"


async def test_signed_pagination_is_scoped_and_complete(admin_api):
    api = admin_api
    await api.login()
    for name in ("alpha", "beta", "gamma"):
        document = demo_document().model_dump(mode="json")
        document["id"] = name
        assert (await api.client.post(BASE + "/flows", json={"document": document})).status_code == 201
    first = (await api.client.get(BASE + "/flows", params={"limit": 2})).json()
    assert [item["id"] for item in first["items"]] == ["alpha", "beta"]
    second = (await api.client.get(BASE + "/flows", params={"cursor": first["next_cursor"], "limit": 2})).json()
    assert [item["id"] for item in second["items"]] == ["gamma"] and second["next_cursor"] is None
    assert (await api.client.get(BASE + "/users/locations", params={"cursor": first["next_cursor"]})).status_code == 422
    assert (await api.client.get(BASE + "/flows", params={"cursor": first["next_cursor"] + "x"})).status_code == 422
    assert (await api.client.get(BASE + "/flows", params={"limit": 101})).status_code == 422


async def test_preview_never_calls_live_delegates_or_persists_sessions(admin_api, monkeypatch):
    from manashelper.modules.student_questions.survey_delegates import SurveyDelegates

    async def forbidden(*args, **kwargs):
        raise AssertionError("Live delegate was called")

    monkeypatch.setattr(SurveyDelegates, "has_submitted", forbidden)
    monkeypatch.setattr(SurveyDelegates, "submit", forbidden)
    api = admin_api
    await api.login()
    body = {
        "document": demo_document().model_dump(mode="json"),
        "user": {"id": 123, "chat_id": 123, "locale": "en", "theme": "basic"},
        "eders_enabled": False,
        "delegate_results": {"student_questions.has_submitted": {"outcome": "success", "values": {"submitted": False}}},
    }
    response = await api.client.post(BASE + "/flows/ui_flow_demo/preview", json=body)
    assert response.status_code == 200 and response.json()["node_id"] == "menu" and not response.json()["issues"]
    body["delegate_results"] = {}
    response = await api.client.post(BASE + "/flows/ui_flow_demo/preview", json=body)
    assert response.status_code == 200 and response.json()["issues"]
    action = body["document"]["nodes"][0]
    action.update(
        delegate="student_questions.submit",
        results={},
        arguments={
            name: {"kind": "literal", "value": value}
            for name, value in {
                "user_id": 123,
                "course": "1",
                "had_questions": False,
                "overwrite": False,
                "questions": None,
                "found_answers": None,
                "answer_sources": None,
                "wants_beta": False,
            }.items()
        },
        outcomes={"success": "menu", "already_submitted": "menu"},
    )
    body["delegate_results"] = {"student_questions.submit": {"outcome": "success", "values": {}}}
    response = await api.client.post(BASE + "/flows/ui_flow_demo/preview", json=body)
    assert response.status_code == 200 and response.json()["node_id"] == "menu" and not response.json()["issues"]
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 0
        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 0


async def test_monitoring_exposes_metadata_without_form_answers(admin_api):
    from tests.modules.ui_flows.factories import button, entered_text

    api = admin_api
    await api.login()
    await publish_demo(api)
    user = RuntimeUser(api.user_id, api.user_id)
    async with api.container() as request:
        dialogs = await request.get(DialogService)
        result = await dialogs.start("ui_flow_demo", user, 7000)
        result = await dialogs.handle(button(result.state, 7001, "form"), user)
        await dialogs.handle(entered_text(result.state, 7002, "secret form answer"), user)
    locations = await api.client.get(BASE + "/users/locations")
    history = await api.client.get(BASE + f"/users/{api.user_id}/transitions", params={"limit": 2})
    assert locations.status_code == history.status_code == 200
    assert locations.json()["items"][0]["node_id"] == "confirm"
    assert history.json()["next_cursor"]
    assert "secret form answer" not in locations.text + history.text
    assert "data" not in locations.json()["items"][0]


async def test_login_page_does_not_put_ticket_into_query_or_storage(admin_api):
    response = await admin_api.client.get("/admin/")
    assert response.status_code == 200
    assert "location.hash" in response.text and "history.replaceState" in response.text
    assert "localStorage" not in response.text and "sessionStorage" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


async def test_owned_web_lifespan_never_starts_bot_scheduler_or_migrations(admin_api, monkeypatch):
    from aiogram import Bot, Dispatcher
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from alembic import command
    from manashelper.platform.web.application import create_admin_app as create_app

    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP startup invoked a bot or migration entry point")

    monkeypatch.setattr(Bot, "__init__", forbidden)
    monkeypatch.setattr(Dispatcher, "start_polling", forbidden)
    monkeypatch.setattr(AsyncIOScheduler, "start", forbidden)
    monkeypatch.setattr(command, "upgrade", forbidden)
    app = create_app(admin_api.app[SETTINGS_KEY])
    async with aiohttp_client(app) as client:
        assert (await client.get("/admin/")).status_code == 200
        assert (await client.get(BASE + "/flows")).status_code == 401


async def test_editor_catalog_and_schema_errors_are_safe_and_specific(admin_api):
    api = admin_api
    assert (await api.client.get(BASE + "/catalog")).status_code == 401
    await api.login()
    catalog = (await api.client.get(BASE + "/catalog")).json()
    item = next(item for item in catalog["texts"] if item["key"] == "common.cancel")
    assert set(item["translations"]) == set(item["themes"]["halloween"]) == {"en", "ru", "ky", "tr", "zh"}
    assert catalog["capability_fields"]["eders_enabled"]["type"] == "boolean"
    document = demo_document().model_dump(mode="json")
    document["nodes"][1]["keyboard"] = "private-secret-unsupported-keyboard"
    response = await api.client.post(BASE + "/flows/ui_flow_demo/validate", json={"document": document})
    assert response.status_code == 422 and "private-secret" not in response.text
    assert any("/nodes/1/" in issue["path"] for issue in response.json()["issues"])


@pytest.mark.parametrize("content_type", [None, "application/json", "application/vnd.manashelper+json"])
async def test_json_body_media_types_preserve_existing_contract(admin_api, content_type):
    api = admin_api
    await api.login()
    document = demo_document().model_dump(mode="json")
    headers = {} if content_type is None else {"Content-Type": content_type}
    response = await api.client.post(BASE + "/flows", content=json.dumps({"document": document}), headers=headers)
    assert response.status_code == 201, response.text
    assert (await api.client.get(BASE + "/flows/ui_flow_demo")).status_code == 200


async def test_non_json_media_type_is_rejected_without_creating_a_scenario(admin_api):
    api = admin_api
    await api.login()
    document = demo_document().model_dump(mode="json")
    document["nodes"][1]["text"] = [{"kind": "inline", "translations": {"en": "private media-type payload"}}]
    response = await api.client.post(
        BASE + "/flows", content=json.dumps({"document": document}), headers={"Content-Type": "text/plain"}
    )
    assert response.status_code == 422
    assert "private media-type payload" not in response.text
    assert (await api.client.get(BASE + "/flows/ui_flow_demo")).status_code == 404


async def test_malformed_json_error_does_not_echo_body_or_create_a_scenario(admin_api):
    api = admin_api
    await api.login()
    raw = '{"document":{"id":"private-json-body","nodes":['
    response = await api.client.post(BASE + "/flows", content=raw, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert "private-json-body" not in response.text
    assert response.json()["issues"][0]["code"] == "schema_json_invalid"
    assert (await api.client.get(BASE + "/flows")).json()["items"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/flows/demo/versions/private-invalid-integer",
        "/users/private-invalid-integer/location",
        "/users/private-invalid-integer/transitions",
    ],
)
async def test_integer_path_errors_are_validated_and_redacted(admin_api, path):
    await admin_api.login()
    response = await admin_api.client.get(BASE + path)
    assert response.status_code == 422
    assert "private-invalid-integer" not in response.text
    assert all(issue["path"].startswith("/path/") for issue in response.json()["issues"])


async def test_built_editor_serves_only_assets_and_keeps_api_protected(admin_api, tmp_path):
    from manashelper.platform.web.application import create_admin_app as create_app

    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text('<div id="app"></div><script src="/admin/assets/editor.js"></script>')
    (assets / "editor.js").write_text("console.log('test bundle')")
    outside = tmp_path.parent / "private-assets"
    outside.mkdir()
    (outside / "private.js").write_text("private asset outside the build")
    (assets / "file-link.js").symlink_to(outside / "private.js")
    (assets / "directory-link").symlink_to(outside, target_is_directory=True)
    app = create_app(admin_api.app[SETTINGS_KEY], admin_api.container, ui_directory=tmp_path)
    async with aiohttp_client(app) as client:
        page = await client.get("/admin/")
        assert page.status_code == 200 and "editor.js" in page.text
        assert "script-src 'self'" in page.headers["content-security-policy"]
        assert (await client.get("/admin/assets/editor.js")).status_code == 200
        assert (await client.get("/admin/src/main.ts")).status_code == 404
        assert (await client.get("/admin/assets/%2e%2e/index.html")).status_code == 404
        assert (await client.get("/admin/assets/file-link.js")).status_code == 404
        assert (await client.get("/admin/assets/directory-link/private.js")).status_code == 404
        assert (await client.get(BASE + "/catalog")).status_code == 401


async def test_return_flow_with_automatic_entry_cannot_be_published_via_http(admin_api):
    api = admin_api
    await api.login()
    document = demo_document().model_dump(mode="json")
    next(node for node in document["nodes"] if node["id"] == "done")["return_flow"] = document["id"]
    assert (await api.client.post(BASE + "/flows", json={"document": document})).status_code == 201
    response = await api.client.post(BASE + "/flows/ui_flow_demo/validate", json={"document": document})
    assert response.json()["issues"][0]["code"] == "invalid_return_entry"
    assert (
        await api.client.post(BASE + "/flows/ui_flow_demo/publish", json={"expected_revision": 0})
    ).status_code == 422


async def test_survey_return_is_publishable_and_preview_remains_a_stub(admin_api):
    from manashelper.modules.food_menu.ui_scenarios import food_menu_notification_scenario
    from manashelper.modules.notifications.ui_scenarios import notifications_document
    from manashelper.modules.schedule.ui_scenarios import schedule_scenarios
    from manashelper.modules.student_questions.flow import survey_document
    from manashelper.modules.ui_flows.menus import main_menu_document
    from manashelper.modules.users.ui_scenarios import user_scenarios
    from manashelper.platform.telegram.ui_scenarios import settings_document

    api = admin_api
    await api.login()
    for document in (
        *user_scenarios(),
        *schedule_scenarios(),
        food_menu_notification_scenario(),
        notifications_document(),
        settings_document(),
        main_menu_document(),
        survey_document(),
    ):
        response = await api.client.post(BASE + "/flows", json={"document": document.model_dump(mode="json")})
        assert response.status_code == 201
        response = await api.client.post(BASE + f"/flows/{document.id}/publish", json={"expected_revision": 0})
        assert response.status_code == 200, response.text
    response = await api.client.post(
        BASE + "/flows/student_questions/preview",
        json={
            "document": survey_document().model_dump(mode="json"),
            "node_id": "thanks",
            "user": {"id": api.user_id, "chat_id": api.user_id, "locale": "ru", "theme": "basic"},
            "eders_enabled": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["issues"] == [] and body["screen"]["return_flow"] == "main_menu"
    assert body["node_id"] == "thanks"
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 0
