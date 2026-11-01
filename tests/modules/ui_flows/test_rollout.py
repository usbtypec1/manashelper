import asyncio

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select

from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.infrastructure.orm import UiFlowEvent, UiScreenDelivery, UiUserLocation
from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.catalog import i18n
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.delivery import Screen
from ui_flows.domain.state import RuntimeUser

BASE = "/admin/api/v1"


async def switch(container, author, mode):
    await (await container.get(FlowTelegramCoordinator)).install_defaults(author)
    async with container() as request:
        service = await request.get(RolloutService)
        return await service.set(mode, (await service.get()).revision, author)


async def current(container, user):
    async with container() as request:
        return await (await request.get(DialogService)).active(RuntimeUser(user, user))


async def press(harness, pool, user, id, update_id):
    async with pool() as session:
        delivery = await session.scalar(
            select(UiScreenDelivery)
            .where(UiScreenDelivery.chat_id == user)
            .order_by(UiScreenDelivery.update_id.desc())
            .limit(1)
        )
        screen = Screen.model_validate(delivery.screen)
        index = [item.id for row in screen.buttons for item in row].index(id)
    await harness.callback(
        UiFlowCallback(token=delivery.token, index=index).pack(), delivery.message_id, update_id, user_id=user
    )


async def test_rollout_api_requires_auth_csrf_ready_publications_and_revision(admin_api):
    api = admin_api
    assert (await api.client.get(BASE + "/rollout")).status_code == 401
    await api.login()
    initial = (await api.client.get(BASE + "/rollout")).json()
    assert initial["mode"] == "admin" and initial["revision"] == initial["active_dialogs"] == 0
    assert (await api.client.put(BASE + "/rollout", json={"mode": "all", "expected_revision": 0})).status_code == 422
    await (await api.container.get(FlowTelegramCoordinator)).install_defaults(api.user_id)
    assert (
        await api.client.put(
            BASE + "/rollout", json={"mode": "all", "expected_revision": 0}, headers={"Origin": "https://wrong.test"}
        )
    ).status_code == 403
    response = await api.client.put(BASE + "/rollout", json={"mode": "all", "expected_revision": 0})
    assert response.status_code == 200 and response.json()["updated_by"] == api.user_id
    assert response.json()["mode"] == "all" and response.json()["revision"] == 1
    assert (await api.client.put(BASE + "/rollout", json={"mode": "off", "expected_revision": 0})).status_code == 409
    assert (await api.client.get(BASE + "/rollout")).json()["mode"] == "all"
    assert (await api.client.put(BASE + "/rollout", json={"mode": "off", "expected_revision": 1})).status_code == 200
    assert (
        await api.client.put(BASE + "/rollout", json={"mode": "invalid", "expected_revision": 2})
    ).status_code == 422


@pytest.mark.parametrize("rollback_mode", ["off", "admin"])
async def test_public_survey_drains_after_rollback_and_new_users_keep_legacy(telegram_flow, rollback_mode):
    harness, container, pool = telegram_flow
    await switch(container, harness.user_id, "all")
    user, newcomer = harness.user_id + 1, harness.user_id + 2
    await harness.message("/start student_questions", 100, user_id=user)
    original = await current(container, user)
    await press(harness, pool, user, "year_1", 101)
    await switch(container, harness.user_id, rollback_mode)
    await harness.message("/start", 102, user_id=newcomer)
    assert await current(container, newcomer) is None
    await harness.message("/start student_questions", 103, user_id=user)
    restored = await current(container, user)
    assert restored.id == original.id and restored.node_id == "search"
    await press(harness, pool, user, "no", 104)
    await press(harness, pool, user, "yes", 105)
    assert await current(container, user) is None
    async with pool() as session:
        assert (await session.get(StudentQuestionsResponse, user)).wants_beta
        assert (await session.get(UiFlowEvent, 105)).result_session_id is None
        assert (await session.get(UiUserLocation, newcomer)).owner == "legacy"
    await harness.message("/start", 106, user_id=user)
    assert await current(container, user) is None
    if rollback_mode == "admin":
        await harness.message("/start", 107)
        assert (await current(container, harness.user_id)).flow_id == "main_menu"


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
async def test_all_users_get_localized_menu_and_survey_and_cannot_open_admin(telegram_flow, locale):
    harness, container, pool = telegram_flow
    user = harness.user_id + 1
    async with pool.begin() as session:
        session.add(User(id=user, full_name="Public user", locale=locale))
    await switch(container, harness.user_id, "all")
    await harness.message("/start", 100, user_id=user)
    assert (await current(container, user)).flow_id == "main_menu"
    with i18n.context(), i18n.use_locale(locale):
        label = i18n.gettext("menu.study")
        prompt = i18n.gettext("student_questions.course_prompt")
    await harness.message(label, 101, user_id=user)
    assert (await current(container, user)).node_id == "study"
    await harness.message("/start student_questions", 102, user_id=user)
    assert any(isinstance(call, SendMessage) and call.chat_id == user and prompt in call.text for call in harness.calls)
    before = await current(container, user)
    await harness.message("/editor", 103, user_id=user)
    assert await current(container, user) == before
    await harness.message("/start", 104, user_id=user, chat_type="group")
    assert await current(container, user) == before


async def test_publication_and_rollback_only_change_new_public_survey_sessions(telegram_flow):
    harness, container, pool = telegram_flow
    await switch(container, harness.user_id, "all")
    users = [harness.user_id + index for index in (1, 2, 3)]
    await harness.message("/start student_questions", 100, user_id=users[0])
    async with container() as request:
        flows = await request.get(FlowService)
        draft = await flows.get("student_questions")
        draft.document.layout["course"].x += 50
        saved = await flows.save(draft.document, draft.revision)
        await flows.publish("student_questions", saved.revision, harness.user_id)
    await harness.message("/start student_questions", 101, user_id=users[1])
    async with container() as request:
        await (await request.get(FlowService)).activate("student_questions", 1, 2)
    await harness.message("/start student_questions", 102, user_id=users[2])
    assert [(await current(container, user)).flow_version for user in users] == [1, 2, 1]
    await press(harness, pool, users[1], "year_2", 103)
    assert (await current(container, users[1])).flow_version == 2


async def test_rollout_update_waits_for_a_launch_transaction(telegram_flow):
    harness, container, pool = telegram_flow
    entered, release = asyncio.Event(), asyncio.Event()

    async def admitted_launch():
        async with container() as request:
            assert await (await request.get(RolloutService)).allows(harness.user_id, lock=True)
            entered.set()
            await release.wait()

    async def disable():
        async with container() as request:
            return await (await request.get(RolloutService)).set("off", 0, harness.user_id)

    launch = asyncio.create_task(admitted_launch())
    await asyncio.wait_for(entered.wait(), 5)
    change = asyncio.create_task(disable())
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(change), 0.1)
    finally:
        release.set()
    await asyncio.wait_for(launch, 5)
    assert (await asyncio.wait_for(change, 5)).mode == "off"
