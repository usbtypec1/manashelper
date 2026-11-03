import pytest
from sqlalchemy import func, select

from manashelper.modules.food_menu.ui_scenarios import food_menu_notification_scenario
from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.ui_delegates import NotificationUiDelegates
from manashelper.modules.notifications.ui_scenarios import notifications_document
from manashelper.modules.ui_flows.infrastructure.orm import UiFlowEvent
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.request import catalog_request
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ButtonEvent

USER_ID = 991_802
SETTINGS = ("schedule_changes", "exam_grades", "lesson_skips")


async def seed(pool):
    async with pool.begin() as session:
        session.add(User(id=USER_ID, full_name="Notification test", locale="tr", theme="halloween"))
    async with container_for(pool) as container, catalog_request(container) as request:
        flows = await request.get(FlowService)
        for document in (food_menu_notification_scenario(), notifications_document()):
            await flows.create(document)
            await flows.publish(document.id, 0, USER_ID)


def event(state, update, button):
    return ButtonEvent(
        kind="button",
        update_id=update,
        user_id=USER_ID,
        chat_id=USER_ID,
        session_id=str(state.id),
        expected_revision=state.revision,
        button_id=button,
    )


async def start(container, update):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).start("notifications_menu", user, update)


async def press(container, state, update, button):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).handle(event(state, update, button), user)


@pytest.mark.parametrize("setting", SETTINGS)
async def test_default_settings_and_first_toggle_survive_new_container(isolated_flow_pool, setting):
    pool = isolated_flow_pool
    await seed(pool)
    async with container_for(pool) as first:
        waiting = await start(first, 81000)
        assert all(waiting.state.data[name] is True for name in SETTINGS)
        changed = await press(first, waiting.state, 81001, setting)
        assert {name: changed.state.data[name] for name in SETTINGS} == {name: name != setting for name in SETTINGS}
    async with container_for(pool) as restarted, catalog_request(restarted) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        restored = await (await request.get(DialogService)).get(changed.state.id, user)
        assert restored == changed.state
    async with pool() as observer:
        saved = await observer.get(NotificationSettings, USER_ID)
        assert {name: getattr(saved, f"{name}_enabled") for name in SETTINGS} == {
            name: name != setting for name in SETTINGS
        }


async def test_failed_toggle_rolls_back_preference_position_and_receipt(isolated_flow_pool, monkeypatch):
    pool = isolated_flow_pool
    await seed(pool)
    original = NotificationUiDelegates.toggle_setting

    async def fail_after_toggle(self, context, arguments):
        await original(self, context, arguments)
        raise RuntimeError("failure after toggle")

    async with container_for(pool) as container:
        waiting = await start(container, 81100)
        with monkeypatch.context() as patch:
            patch.setattr(NotificationUiDelegates, "toggle_setting", fail_after_toggle)
            async with catalog_request(container) as request:
                dialogs = await request.get(DialogService)
                user = await FlowTelegramCoordinator._user(request, USER_ID)
                with pytest.raises(RuntimeError, match="failure after toggle"):
                    await dialogs.handle(event(waiting.state, 81101, "exam_grades"), user)
                assert await dialogs.get(waiting.state.id, user) == waiting.state
        async with pool() as observer:
            saved = await observer.get(NotificationSettings, USER_ID)
            assert all(getattr(saved, f"{name}_enabled") for name in SETTINGS)
            assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 1
        result = await press(container, waiting.state, 81101, "exam_grades")
        assert result.state.data["exam_grades"] is False


async def test_food_call_returns_to_notifications_and_keeps_locale_and_theme(isolated_flow_pool):
    await seed(isolated_flow_pool)
    async with container_for(isolated_flow_pool) as container:
        waiting = await start(container, 81200)
        child = await press(container, waiting.state, 81201, "food")
        assert (child.state.flow_id, child.state.node_id, len(child.state.frames)) == (
            "food_menu_notifications",
            "menu",
            1,
        )
        result = await press(container, child.state, 81202, "back")
        assert (result.state.flow_id, result.state.node_id, result.state.frames) == ("notifications_menu", "menu", ())
        async with catalog_request(container) as request:
            user = await FlowTelegramCoordinator._user(request, USER_ID)
            flow = await (await request.get(FlowService)).version(result.state.flow_id, result.state.flow_version)
            screen = FlowRenderer().render(flow.document, result, user, {"eders_enabled": False})
        assert (screen.locale, screen.theme) == ("tr", "halloween")
        assert "eders" not in [button.id for row in screen.buttons for button in row]
        assert all(result.state.data[name] is True for name in SETTINGS)
