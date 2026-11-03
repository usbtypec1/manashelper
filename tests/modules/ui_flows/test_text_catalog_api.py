from sqlalchemy import func, select

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession
from manashelper.modules.ui_flows.menus import main_menu_document
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer
from manashelper.modules.users.ui_scenarios import user_scenarios
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.telegram.ui_scenarios import settings_document
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.state import RuntimeUser

BASE = "/admin/api/v1"


def edit(draft, key, text):
    entry = next(item for item in draft["document"]["entries"] if item["key"] == key)
    for variant in entry["variants"]:
        if variant["locale"] == "en" and variant["theme"] == "basic":
            variant["text"] = text
    return entry


async def test_catalog_authorization_validation_and_conflict_preserve_draft(admin_api):
    api = admin_api
    assert (await api.client.get(BASE + "/texts")).status_code == 401
    await api.login()
    original = (await api.client.get(BASE + "/texts")).json()
    assert len(original["document"]["entries"]) == 356
    entry = edit(original, "menu.food", "A new cafeteria")
    response = await api.client.put(
        BASE + "/texts/menu.food",
        json={"entry": entry, "expected_revision": 0},
        headers={"Origin": "https://other.test"},
    )
    assert response.status_code == 403
    saved = await api.client.put(BASE + "/texts/menu.food", json={"entry": entry, "expected_revision": 0})
    assert saved.status_code == 200 and saved.json()["revision"] == 1
    stale = await api.client.put(BASE + "/texts/menu.food", json={"entry": entry, "expected_revision": 0})
    assert stale.status_code == 409
    entry["variants"][0]["text"] = "<script>private-invalid-template</script>"
    invalid = await api.client.put(BASE + "/texts/menu.food", json={"entry": entry, "expected_revision": 1})
    assert invalid.status_code == 422 and "private-invalid-template" not in invalid.text
    assert (await api.client.get(BASE + "/texts")).json()["revision"] == 1


async def test_catalog_publication_pins_scenarios_and_historical_preview(admin_api):
    api = admin_api
    await api.login()
    for dependency in (*user_scenarios(), settings_document()):
        response = await api.client.post(BASE + "/flows", json={"document": dependency.model_dump(mode="json")})
        assert response.status_code == 201, response.text
        response = await api.client.post(BASE + f"/flows/{dependency.id}/publish", json={"expected_revision": 0})
        assert response.status_code == 200, response.text
    document = main_menu_document().model_dump(mode="json")
    assert (await api.client.post(BASE + "/flows", json={"document": document})).status_code == 201
    first = (await api.client.post(BASE + "/flows/main_menu/publish", json={"expected_revision": 0})).json()
    assert first["text_catalog_release"] == 1
    user = RuntimeUser(api.user_id, api.user_id)
    async with catalog_request(api.container) as request:
        old = await (await request.get(DialogService)).start("main_menu", user, 117000)
    baseline = (await api.client.get(BASE + "/catalog")).json()
    old_label = next(item["translations"]["en"] for item in baseline["texts"] if item["key"] == "menu.food")
    draft = (await api.client.get(BASE + "/texts")).json()
    entry = edit(draft, "menu.food", "Updated cafeteria")
    assert (
        await api.client.put(BASE + "/texts/menu.food", json={"entry": entry, "expected_revision": 0})
    ).status_code == 200
    assert (await api.client.post(BASE + "/texts/publish", json={"expected_revision": 1})).json()["id"] == 2
    assert (await api.client.post(BASE + "/texts/publish", json={"expected_revision": 1})).json()["id"] == 2
    historical = (await api.client.get(BASE + "/catalog?text_catalog_release=1")).json()
    assert next(item["translations"]["en"] for item in historical["texts"] if item["key"] == "menu.food") == old_label
    preview = {
        "document": document,
        "user": {"id": api.user_id, "chat_id": api.user_id, "locale": "en", "theme": "basic"},
        "eders_enabled": False,
    }
    current = (await api.client.post(BASE + "/flows/main_menu/preview", json=preview)).json()
    assert current["screen"]["buttons"][0][0]["label"] == "Updated cafeteria"
    prior = (
        await api.client.post(BASE + "/flows/main_menu/preview", json={**preview, "text_catalog_release": 1})
    ).json()
    assert prior["screen"]["buttons"][0][0]["label"] == old_label
    assert (
        await api.client.put(BASE + "/flows/main_menu/draft", json={"document": document, "expected_revision": 0})
    ).status_code == 200
    second = (await api.client.post(BASE + "/flows/main_menu/publish", json={"expected_revision": 1})).json()
    assert second["text_catalog_release"] == 2
    async with catalog_request(api.container) as request:
        flows = await request.get(FlowService)
        active = await (await request.get(DialogService)).active(user)
        assert active.flow_version == old.state.flow_version == 1
        pinned = await flows.version("main_menu", active.flow_version)
        snapshot = await (await request.get(TextCatalogService)).version(pinned.text_catalog_release)
        with i18n.use_catalog(snapshot):
            screen = FlowRenderer().render(pinned.document, old, user, {"eders_enabled": False})
        assert screen.buttons[0][0].label == old_label
    assert (
        await api.client.post(BASE + "/flows/main_menu/activate", json={"version": 1, "expected_published_version": 2})
    ).status_code == 200
    assert (
        await api.client.post(BASE + "/texts/activate", json={"release_id": 1, "expected_current_release": 2})
    ).status_code == 200
    assert (
        await api.client.post(BASE + "/texts/activate", json={"release_id": 2, "expected_current_release": 2})
    ).status_code == 409
    versions = (await api.client.get(BASE + "/texts/releases")).json()["items"]
    assert [item["id"] for item in versions] == [2, 1]
    async with api.pool() as session:
        assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 1


async def test_request_snapshot_stays_fixed_while_another_request_publishes(admin_api):
    api = admin_api
    await api.login()
    async with catalog_request(api.container) as request:
        initial = i18n.gettext("menu.food", locale="en")
        draft = (await api.client.get(BASE + "/texts")).json()
        entry = edit(draft, "menu.food", "Concurrent publication")
        assert (
            await api.client.put(BASE + "/texts/menu.food", json={"entry": entry, "expected_revision": 0})
        ).status_code == 200
        assert (await api.client.post(BASE + "/texts/publish", json={"expected_revision": 1})).status_code == 200
        assert i18n.gettext("menu.food", locale="en") == initial
        assert (await (await request.get(TextCatalogService)).current()).release_id == 1
    async with catalog_request(api.container):
        assert i18n.gettext("menu.food", locale="en") == "Concurrent publication"
