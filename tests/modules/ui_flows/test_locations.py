from sqlalchemy import select

from manashelper.modules.ui_flows.infrastructure.locations import LocationRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiUserLocation, UiUserTransition
from manashelper.modules.ui_flows.menus import main_menu_document
from tests.modules.ui_flows.factories import button
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.locations import LocationService
from ui_flows.domain.state import RuntimeUser


async def test_legacy_metadata_is_monotonic_deduplicated_and_unknown_after_restart(session, flow_user):
    service = LocationService(LocationRepository(session))
    user_id = flow_user.id
    await service.observe(user_id, user_id, 99, "old", "OldForm:step")
    await service.observe(user_id, user_id, 100, "obis", "ObisCredentialsForm:student_number")
    await service.observe(user_id, user_id, 101, "obis", "ObisCredentialsForm:password")
    await service.observe(user_id, user_id, 101, "wrong", "wrong")
    await service.observe(user_id, user_id, 99, "stale", "stale")
    location = await session.get(UiUserLocation, user_id, populate_existing=True)
    assert location.owner == "legacy" and location.legacy_state == "ObisCredentialsForm:password"
    transitions = list(await session.scalars(select(UiUserTransition).order_by(UiUserTransition.id)))
    assert len(transitions) == 3 and transitions[-1].from_step == "ObisCredentialsForm:student_number"
    observed_at = location.updated_at
    await service.forget_legacy()
    await session.refresh(location)
    assert location.owner == "unknown" and location.updated_at == observed_at
    assert location.legacy_state == "ObisCredentialsForm:password"
    assert not {"data", "password", "text"}.intersection(UiUserLocation.__table__.columns.keys())
    assert not {"data", "password", "text"}.intersection(UiUserTransition.__table__.columns.keys())


async def test_group_observations_are_ignored(session, flow_user):
    service = LocationService(LocationRepository(session))
    await service.observe(flow_user.id, -1000, 100, "group", None)
    assert await session.get(UiUserLocation, flow_user.id) is None


async def test_fresh_smaller_update_id_is_observed_after_an_idle_gap(session, flow_user):
    service = LocationService(LocationRepository(session))
    await service.observe(flow_user.id, flow_user.id, 1000, "first", "FirstForm:step")
    await service.observe(flow_user.id, flow_user.id, 7, "second", "SecondForm:step")
    location = await session.get(UiUserLocation, flow_user.id)
    assert location.update_id == 7 and location.legacy_state == "SecondForm:step"


async def test_runtime_owns_active_steps_and_handoff_finishes_one_trace(admin_api):
    api = admin_api
    user = RuntimeUser(api.user_id, api.user_id)
    async with api.container() as request:
        flows = await request.get(FlowService)
        await flows.create(main_menu_document())
        await flows.publish("main_menu", 0, api.user_id)
        dialogs = await request.get(DialogService)
        started = await dialogs.start("main_menu", user, 100)
        observer = await request.get(LocationService)
        await observer.observe(user.id, user.id, 101, "late legacy", "OtherForm:step")
    async with api.pool() as session:
        location = await session.get(UiUserLocation, user.id)
        assert location.owner == "runtime" and location.session_id == started.state.id
    async with api.container() as request:
        ended = await (await request.get(DialogService)).handle(button(started.state, 102, "food"), user)
        assert ended.state.status == "handed_off"
        await (await request.get(LocationService)).observe(user.id, user.id, 102, "food_menu", None)
    async with api.pool() as session:
        location = await session.get(UiUserLocation, user.id)
        assert location.owner == "legacy" and location.handler == "food_menu" and location.session_id is None
        traces = list(await session.scalars(select(UiUserTransition).order_by(UiUserTransition.id)))
        assert len(traces) == 2 and traces[-1].outcome == "handed_off"
        assert traces[-1].flow_id == "main_menu" and traces[-1].flow_version == 1


async def test_runtime_location_advances_when_a_fresh_update_id_is_smaller(admin_api):
    api = admin_api
    user = RuntimeUser(api.user_id, api.user_id)
    async with api.container() as request:
        flows = await request.get(FlowService)
        await flows.create(main_menu_document())
        await flows.publish("main_menu", 0, api.user_id)
        dialogs = await request.get(DialogService)
        started = await dialogs.start("main_menu", user, 1000)
        await dialogs.handle(button(started.state, 7, "study"), user)
    async with api.pool() as session:
        location = await session.get(UiUserLocation, user.id)
        assert location.update_id == 7 and location.owner == "runtime"


async def test_unknown_registered_user_is_listed_and_legacy_state_does_not_expose_data(admin_api):
    api = admin_api
    await api.login()
    result = (await api.client.get("/admin/api/v1/users/locations")).json()
    assert len(result["items"]) == 1 and result["items"][0]["owner"] == "unknown"
    assert result["items"][0]["updated_at"] is None
    async with api.container() as request:
        await (await request.get(LocationService)).observe(
            api.user_id, api.user_id, 100, "obis", "ObisCredentialsForm:password"
        )
    response = await api.client.get(f"/admin/api/v1/users/{api.user_id}/location")
    assert response.json()["owner"] == "legacy" and response.json()["legacy_state"] == "ObisCredentialsForm:password"
    assert "data" not in response.json()
    assert (await api.client.get("/admin/api/v1/users/999999/location")).status_code == 404


async def test_real_legacy_fsm_is_observed_without_copying_passwords(telegram_flow, monkeypatch):
    from manashelper.modules.obis.application.obis import ObisService
    from manashelper.modules.obis.errors import ObisLoginError
    from manashelper.modules.obis.presentation.callbacks import ObisAction, ObisCallback
    from manashelper.modules.ui_flows.presentation.observation import ObservationCoordinator
    from manashelper.platform.telegram.audit.orm import ActionLog

    async def reject(*args, **kwargs):
        raise ObisLoginError("Synthetic failed login")

    monkeypatch.setattr(ObisService, "save_credentials", reject)
    harness, container, pool = telegram_flow
    await harness.message("/start", 100)
    await harness.callback(ObisCallback(action=ObisAction.ACCEPT_TERMS).pack(), 1000, 101)
    await harness.message("20990101", 102)
    async with pool() as session:
        location = await session.get(UiUserLocation, harness.user_id)
        assert location.owner == "legacy" and location.legacy_state == "ObisCredentialsForm:password"
    await harness.message("secret-password-not-for-metadata", 103)
    async with pool() as session:
        location = await session.get(UiUserLocation, harness.user_id)
        assert location.legacy_state == "ObisCredentialsForm:student_number"
        rows = list(await session.scalars(select(UiUserTransition)))
        assert "secret-password" not in repr([(row.from_step, row.to_step, row.outcome) for row in rows])
        assert "secret-password-not-for-metadata" not in list(await session.scalars(select(ActionLog.message_text)))
    await (await container.get(ObservationCoordinator)).restart()
    async with pool() as session:
        assert (await session.get(UiUserLocation, harness.user_id)).owner == "unknown"
