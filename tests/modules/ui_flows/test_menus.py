import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select

from manashelper.core.config import get_settings
from manashelper.modules.ui_flows.infrastructure.orm import UiScreenDelivery, UiUserLocation
from ui_flows.application.dialogs import DialogService
from ui_flows.domain.state import RuntimeUser


async def latest(pool):
    async with pool() as session:
        return await session.scalar(select(UiScreenDelivery).order_by(UiScreenDelivery.update_id.desc()).limit(1))


@pytest.mark.parametrize(
    ("feature", "button_id", "studies"),
    [
        ("food_menu", "food", False),
        ("marketplace", "marketplace", False),
        ("settings", "settings", False),
        ("schedule", "schedule", True),
        ("attendance", "attendance", True),
        ("grades", "grades", True),
        ("study_week", "week", True),
        ("eders", "eders", True),
        ("eders_materials", "materials", True),
    ],
)
async def test_imported_menu_opens_existing_features_and_returns_to_runtime(
    telegram_flow, monkeypatch, feature, button_id, studies
):
    import httpx

    from ui_flows.domain.delivery import Screen

    monkeypatch.setenv("MANASHELPER_EDERS_PASSWORD", "synthetic-flag-only")
    get_settings.cache_clear()

    async def no_http(*args, **kwargs):
        raise AssertionError("A menu entry must read snapshots without external HTTP")

    monkeypatch.setattr(httpx.AsyncClient, "request", no_http)
    harness, container, pool = telegram_flow
    await harness.message("/start", 100)
    if studies:
        screen = Screen.model_validate((await latest(pool)).screen)
        label = next(button.label for row in screen.buttons for button in row if button.id == "study")
        await harness.message(label, 101)
    screen = Screen.model_validate((await latest(pool)).screen)
    label = next(button.label for row in screen.buttons for button in row if button.id == button_id)
    await harness.message(label, 102)
    async with pool() as session:
        location = await session.get(UiUserLocation, harness.user_id)
        assert location.owner == "legacy" and location.handler == feature
    assert (await latest(pool)).status == "sent"
    from manashelper.platform.i18n.catalog import i18n

    with i18n.context(), i18n.use_locale("en"):
        back = i18n.gettext("common.back_to_menu")
    await harness.message(back, 103)
    async with container() as request:
        state = await (await request.get(DialogService)).active(RuntimeUser(harness.user_id, harness.user_id))
        assert state.flow_id == "main_menu" and state.node_id == "main"


async def test_disabled_eders_buttons_are_hidden_and_other_users_keep_legacy_start(telegram_flow, monkeypatch):
    from ui_flows.domain.delivery import Screen

    monkeypatch.delenv("MANASHELPER_EDERS_PASSWORD", raising=False)
    get_settings.cache_clear()
    harness, container, pool = telegram_flow
    await harness.message("/start", 100)
    screen = Screen.model_validate((await latest(pool)).screen)
    await harness.message(next(button.label for row in screen.buttons for button in row if button.id == "study"), 101)
    screen = Screen.model_validate((await latest(pool)).screen)
    assert not {"week", "eders", "materials"}.intersection(button.id for row in screen.buttons for button in row)
    await harness.message("/start", 102, user_id=harness.user_id + 1)
    async with pool() as session:
        assert (await session.get(UiUserLocation, harness.user_id + 1)).owner == "legacy"
    assert any(isinstance(call, SendMessage) for call in harness.calls)


async def test_inline_handoff_uses_callback_user_not_bot_message_author(telegram_flow, monkeypatch):
    from manashelper.modules.obis.application.obis import ObisService
    from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
    from ui_flows.application.flows import FlowService
    from ui_flows.domain.delivery import Screen
    from ui_flows.domain.schema import MenuNode

    called = []

    async def cached(service, user_id):
        called.append(user_id)
        return []

    monkeypatch.setattr(ObisService, "get_attendance", cached)
    harness, container, pool = telegram_flow
    await harness.message("/start", 200)
    async with container() as request:
        flows = await request.get(FlowService)
        draft = await flows.get("main_menu")
        for node in draft.document.nodes:
            if isinstance(node, MenuNode):
                node.keyboard = "inline"
        saved = await flows.save(draft.document, draft.revision)
        await flows.publish("main_menu", saved.revision, harness.user_id)
    await harness.message("/start", 201)
    for update_id, button_id in ((202, "study"), (203, "attendance")):
        delivery = await latest(pool)
        screen = Screen.model_validate(delivery.screen)
        index = [button.id for row in screen.buttons for button in row].index(button_id)
        await harness.callback(UiFlowCallback(token=delivery.token, index=index).pack(), delivery.message_id, update_id)
    assert called == [harness.user_id]
    async with pool() as session:
        assert (await session.get(UiUserLocation, harness.user_id)).handler == "attendance"
