import asyncio

import pytest
from sqlalchemy import func, select

from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiTriggerRelease
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.platform.i18n.request import catalog_request
from ui_flows.domain.ingress import TriggerDocument
from ui_flows.errors import FlowConflictError

BASE = "/admin/api/v1/triggers"


async def ready(api):
    await (await api.container.get(FlowTelegramCoordinator)).install_defaults(api.user_id)
    await api.login()


async def test_trigger_api_auth_conflicts_manifest_and_idempotent_rollback(admin_api):
    api = admin_api
    assert (await api.client.get(BASE)).status_code == 401
    await ready(api)
    draft = (await api.client.get(BASE)).json()
    assert len(draft["document"]["bindings"]) == 78 and draft["current_release"] == 1
    body = {"document": draft["document"], "expected_revision": 0}
    assert (await api.client.put(BASE, json=body, headers={"Origin": "https://other.test"})).status_code == 403
    assert (await api.client.put(BASE, json=body, headers={"X-CSRF-Token": "invalid"})).status_code == 403
    assert (await api.client.put(BASE, json=body)).json()["revision"] == 1
    assert (await api.client.put(BASE, json=body)).status_code == 409
    response = await api.client.post(BASE + "/publish", json={"expected_revision": 1})
    assert response.status_code == 200
    release = response.json()
    assert release["id"] == 2
    assert {item["flow_id"] for item in release["manifest"]["scenarios"]} == {
        "main_menu",
        "student_questions",
        "settings",
        "select_locale",
        "select_theme",
    }
    assert all(item["text_catalog_release"] == 1 for item in release["manifest"]["scenarios"])
    assert (
        await api.client.post(BASE + "/activate", json={"release_id": 1, "expected_current_release": 2})
    ).status_code == 200
    assert (await api.client.post(BASE + "/publish", json={"expected_revision": 1})).json()["id"] == 2
    assert (await api.client.get(BASE)).json()["current_release"] == 1
    assert (
        await api.client.post(BASE + "/activate", json={"release_id": 2, "expected_current_release": 2})
    ).status_code == 409
    assert [item["id"] for item in (await api.client.get(BASE + "/releases")).json()["items"]] == [2, 1]


async def test_invalid_trigger_publication_preserves_release_and_reports_sanitized_issues(admin_api):
    api = admin_api
    await ready(api)
    draft = (await api.client.get(BASE)).json()
    copy = {**draft["document"]["bindings"][0], "id": "duplicate"}
    draft["document"]["bindings"].append(copy)
    assert (await api.client.put(BASE, json={"document": draft["document"], "expected_revision": 0})).status_code == 200
    invalid = await api.client.post(BASE + "/publish", json={"expected_revision": 1})
    assert invalid.status_code == 422 and "ambiguous_binding" in invalid.text
    assert (await api.client.get(BASE)).json()["current_release"] == 1
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiTriggerRelease)) == 1


async def test_trigger_concurrent_saves_and_failed_transaction_preserve_committed_release(admin_api):
    api = admin_api
    await ready(api)
    draft = (await api.client.get(BASE)).json()
    document = TriggerDocument.model_validate(draft["document"])

    async def save():
        try:
            async with catalog_request(api.container) as request:
                return await (await request.get(TriggerService)).save(document, 0)
        except FlowConflictError:
            return None

    results = await asyncio.gather(save(), save())
    assert sum(result is not None for result in results) == 1
    with pytest.raises(RuntimeError):
        async with catalog_request(api.container) as request:
            await (await request.get(TriggerService)).publish(1, api.user_id)
            raise RuntimeError("rollback publication")
    assert (await api.client.get(BASE)).json()["current_release"] == 1
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiTriggerRelease)) == 1
