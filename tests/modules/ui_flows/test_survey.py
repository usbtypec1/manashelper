import asyncio

import pytest
from aiogram.methods import AnswerCallbackQuery, SendMessage
from sqlalchemy import func, select

from manashelper.modules.student_questions.callbacks import (
    StudentQuestionsAnswerCallback,
    StudentQuestionsControlAction,
    StudentQuestionsControlCallback,
    StudentQuestionsStep,
)
from manashelper.modules.student_questions.flow import survey_document
from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.student_questions.router import SESSION_KEY, StudentQuestionsForm
from manashelper.modules.student_questions.service import StudentCourse
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiScreenDelivery
from manashelper.platform.i18n.catalog import i18n
from tests.modules.ui_flows.factories import button, document, publish_examples, runtime
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.delivery import Screen
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import StaleEventError


async def current(pool):
    async with pool() as session:
        return await session.scalar(select(UiScreenDelivery).order_by(UiScreenDelivery.update_id.desc()).limit(1))


async def press(harness, pool, id, update_id):
    delivery = await current(pool)
    screen = Screen.model_validate(delivery.screen)
    index = [item.id for row in screen.buttons for item in row].index(id)
    from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback

    await harness.callback(UiFlowCallback(token=delivery.token, index=index).pack(), delivery.message_id, update_id)


async def active(container, user_id):
    async with container() as request:
        return await (await request.get(DialogService)).active(RuntimeUser(user_id, user_id))


def test_production_survey_matches_reviewed_contract_and_all_courses():
    actual = survey_document().model_dump(exclude={"layout"})
    assert actual == document("student_questions").model_dump(exclude={"layout"})
    course = next(node for node in survey_document().nodes if node.id == "course")
    values = {item.assignments["course"].value for row in course.buttons for item in row if item.id != "cancel"}
    assert values == {course.value for course in StudentCourse}


async def test_seed_waits_for_published_root_and_never_overwrites_edits(telegram_flow):
    from manashelper.modules.ui_flows.menus import main_menu_document
    from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
    from ui_flows.errors import FlowNotFoundError

    harness, container, pool = telegram_flow
    async with container() as request:
        await (await request.get(FlowService)).create(main_menu_document())
    coordinator = await container.get(FlowTelegramCoordinator)
    await coordinator.install_defaults(harness.user_id)
    async with container() as request:
        flows = await request.get(FlowService)
        assert (await flows.get("main_menu")).published_version is None
        with pytest.raises(FlowNotFoundError):
            await flows.get("student_questions")
        await flows.publish("main_menu", 0, harness.user_id)
    await coordinator.install_defaults(harness.user_id)
    async with container() as request:
        flows = await request.get(FlowService)
        draft = await flows.get("student_questions")
        draft.document.layout["course"].x = 999
        await flows.save(draft.document, draft.revision)
    await coordinator.install_defaults(harness.user_id)
    async with container() as request:
        draft = await (await request.get(FlowService)).get("student_questions")
        assert draft.revision == 1 and draft.published_version == 1
        assert draft.document.layout["course"].x == 999


@pytest.mark.parametrize("path", ["no_questions", "not_found", "sources"])
@pytest.mark.parametrize("beta", [True, False])
async def test_survey_deep_link_runs_all_branches_and_returns_to_published_menu(telegram_flow, path, beta):
    harness, container, pool = telegram_flow
    await harness.message("/start student_questions", 100)
    assert (await active(container, harness.user_id)).flow_id == "student_questions"
    await press(harness, pool, "year_1", 101)
    await press(harness, pool, "no" if path == "no_questions" else "yes", 102)
    if path != "no_questions":
        await harness.message("   ", 103)
        assert (await active(container, harness.user_id)).node_id == "questions"
        await harness.message("  <question> & details  ", 104)
        await press(harness, pool, "yes" if path == "sources" else "no", 105)
        if path == "sources":
            await harness.message("  student community  ", 106)
    before = await active(container, harness.user_id)
    assert before.node_id == "beta"
    async with pool() as session:
        assert await session.get(StudentQuestionsResponse, harness.user_id) is None
    await press(harness, pool, "yes" if beta else "no", 107)
    following = await active(container, harness.user_id)
    assert following.flow_id == "main_menu" and following.node_id == "main"
    delivery = await current(pool)
    assert delivery.status == "sent"
    with i18n.context(), i18n.use_locale("en"):
        assert i18n.gettext("student_questions.thanks") in delivery.screen["text"]
        assert (i18n.gettext("student_questions.beta_follow_up") in delivery.screen["text"]) is beta
    async with pool() as session:
        saved = await session.get(StudentQuestionsResponse, harness.user_id)
        assert saved.had_questions is (path != "no_questions") and saved.wants_beta is beta
        assert saved.questions == (None if path == "no_questions" else "<question> & details")
        assert saved.found_answers == (None if path == "no_questions" else path == "sources")
        assert saved.answer_sources == ("student community" if path == "sources" else None)
        event = await session.get(UiFlowEvent, 107)
        assert event.session_id == before.id and event.result_session_id == following.id
        assert (await session.get(UiDialogSession, before.id)).status == "completed"
    # Neither an old inline button nor a replay can submit or open a second menu.
    calls = len([call for call in harness.calls if isinstance(call, SendMessage)])
    async with container() as request:
        result = await (await request.get(DialogService)).handle(
            button(before, 107, "yes" if beta else "no"),
            RuntimeUser(harness.user_id, harness.user_id),
            follow_returns=True,
        )
        assert result.outcome == "duplicate" and result.state.id == following.id
    assert len([call for call in harness.calls if isinstance(call, SendMessage)]) == calls


async def test_confirmed_replacement_preserves_previous_response_until_finished(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/start student_questions", 100)
    await press(harness, pool, "year_2", 101)
    await press(harness, pool, "no", 102)
    await press(harness, pool, "no", 103)
    async with pool() as session:
        old = await session.get(StudentQuestionsResponse, harness.user_id)
        previous = (old.course, old.submitted_at)
    await harness.message("/start student_questions", 104)
    assert (await active(container, harness.user_id)).node_id == "overwrite"
    await press(harness, pool, "replace", 105)
    await press(harness, pool, "preparatory", 106)
    await press(harness, pool, "yes", 107)
    await harness.message("new unfinished answer", 108)
    await press(harness, pool, "cancel", 109)
    async with pool() as session:
        old = await session.get(StudentQuestionsResponse, harness.user_id)
        assert (old.course, old.submitted_at) == previous
    await harness.message("/start student_questions", 110)
    await press(harness, pool, "replace", 111)
    await press(harness, pool, "not_student", 112)
    await press(harness, pool, "no", 113)
    async with pool() as session:
        assert (await session.get(StudentQuestionsResponse, harness.user_id)).course == "2"
    await press(harness, pool, "yes", 114)
    async with pool() as session:
        saved = await session.get(StudentQuestionsResponse, harness.user_id)
        assert saved.course == "not_student" and saved.wants_beta
        assert saved.questions is None and saved.submitted_at > previous[1]
        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1


async def test_existing_legacy_survey_continues_and_old_buttons_do_not_cancel_runtime(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/start", 100)
    state = harness.dispatcher.fsm.get_context(bot=harness.bot, chat_id=harness.user_id, user_id=harness.user_id)
    await state.set_state(StudentQuestionsForm.course)
    await state.set_data({SESSION_KEY: "old-survey", "overwrite": False})
    # A repeated deep link remains owned by the existing legacy form.
    await harness.message("/start student_questions", 101)
    assert await state.get_state() == StudentQuestionsForm.course.state
    assert await active(container, harness.user_id) is None
    legacy_id = (await state.get_data())[SESSION_KEY]
    for update, step, answer in (
        (102, StudentQuestionsStep.COURSE, "3"),
        (103, StudentQuestionsStep.SEARCH, "no"),
        (104, StudentQuestionsStep.BETA, "no"),
    ):
        await harness.callback(
            StudentQuestionsAnswerCallback(session_id=legacy_id, step=step, answer=answer).pack(), 42, update
        )
    assert await state.get_state() is None
    async with pool() as session:
        assert (await session.get(StudentQuestionsResponse, harness.user_id)).course == "3"
    await harness.message("/start student_questions", 105)
    current_state = await active(container, harness.user_id)
    for update, payload in (
        (
            106,
            StudentQuestionsAnswerCallback(session_id=legacy_id, step=StudentQuestionsStep.BETA, answer="yes").pack(),
        ),
        (
            107,
            StudentQuestionsControlCallback(session_id=legacy_id, action=StudentQuestionsControlAction.CANCEL).pack(),
        ),
    ):
        await harness.callback(payload, 42, update)
        assert (await active(container, harness.user_id)).id == current_state.id
    assert any(isinstance(call, AnswerCallbackQuery) and call.show_alert for call in harness.calls)


async def test_regular_users_keep_the_five_language_legacy_survey(telegram_flow):
    harness, container, pool = telegram_flow
    other = harness.user_id + 1
    await harness.message("/start student_questions", 100, user_id=other)
    assert await active(container, other) is None
    state = harness.dispatcher.fsm.get_context(bot=harness.bot, chat_id=other, user_id=other)
    assert await state.get_state() == StudentQuestionsForm.course.state


async def test_survey_restores_pinned_version_in_new_container(telegram_flow):
    harness, container, pool = telegram_flow
    await harness.message("/start student_questions", 100)
    await press(harness, pool, "year_5", 101)
    original = await active(container, harness.user_id)
    async with container() as request:
        flows = await request.get(FlowService)
        draft = await flows.get("student_questions")
        draft.document.layout["course"].x += 1
        saved = await flows.save(draft.document, draft.revision)
        await flows.publish("student_questions", saved.revision, harness.user_id)
    async with container_for(pool) as restarted, restarted() as request:
        restored = await (await request.get(DialogService)).active(RuntimeUser(harness.user_id, harness.user_id))
        assert restored == original and restored.flow_version == 1


async def test_invalid_return_rolls_back_final_answer_even_when_error_is_caught(telegram_flow):
    from ui_flows.errors import FlowExecutionError

    harness, container, pool = telegram_flow
    await harness.message("/start student_questions", 100)
    await press(harness, pool, "year_4", 101)
    await press(harness, pool, "no", 102)
    before = await active(container, harness.user_id)
    user = RuntimeUser(harness.user_id, harness.user_id)
    async with container() as request:
        flows = await request.get(FlowService)
        draft = await flows.get("main_menu")
        from ui_flows.domain.schema import ConditionNode

        draft.document.nodes.append(
            ConditionNode.model_validate(
                {
                    "kind": "condition",
                    "id": "entry_gate",
                    "default": "main",
                    "branches": [
                        {
                            "when": {"kind": "exists", "reference": {"kind": "ref", "scope": "user", "field": "id"}},
                            "target": "main",
                        }
                    ],
                }
            )
        )
        draft.document.entry = "entry_gate"
        saved = await flows.save(draft.document, draft.revision)
        await flows.publish("main_menu", saved.revision, harness.user_id)
    async with container() as request:
        with pytest.raises(FlowExecutionError, match="interactive"):
            await (await request.get(DialogService)).handle(button(before, 103, "yes"), user, follow_returns=True)
    async with pool() as session:
        assert await session.get(StudentQuestionsResponse, harness.user_id) is None
        assert await session.get(UiFlowEvent, 103) is None
    assert await active(container, harness.user_id) == before
    async with container() as request:
        await (await request.get(FlowService)).activate("main_menu", 1, 2)
    await press(harness, pool, "yes", 103)
    assert (await active(container, harness.user_id)).flow_id == "main_menu"


@pytest.mark.parametrize("same_update", [True, False])
async def test_concurrent_submit_with_return_opens_one_menu(isolated_flow_pool, same_update):
    from manashelper.modules.users.infrastructure.user import User
    from ui_flows.errors import InvalidEventError

    user = RuntimeUser(991402, 991402)
    async with isolated_flow_pool.begin() as session:
        session.add(User(id=user.id, full_name="Survey concurrency"))
        await session.flush()
        services = runtime(session)
        await publish_examples(services)
        result = await services.dialogs.start("student_questions", user, 10)
        result = await services.dialogs.handle(button(result.state, 11, "year_1"), user)
        result = await services.dialogs.handle(button(result.state, 12, "no"), user)
        before = result.state

    async def finish(update_id):
        try:
            async with isolated_flow_pool.begin() as session:
                return await runtime(session).dialogs.handle(
                    button(before, update_id, "yes"), user, follow_returns=True
                )
        except (StaleEventError, InvalidEventError) as error:
            return error

    results = await asyncio.wait_for(asyncio.gather(finish(13), finish(13 if same_update else 14)), timeout=10)
    if same_update:
        assert {result.outcome for result in results} == {"advanced", "duplicate"}
        assert results[0].state.id == results[1].state.id
    else:
        assert sum(isinstance(item, StaleEventError) for item in results) == 1
    async with isolated_flow_pool() as session:
        assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1
        assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 2
        assert await session.scalar(select(func.count()).select_from(UiFlowEvent)) == 4
