from dataclasses import replace

import pytest
from sqlalchemy import func, select

from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.student_questions.survey_delegates import SurveyDelegates
from manashelper.modules.ui_flows.infrastructure.flows import FlowRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiFlowEvent
from tests.modules.ui_flows.factories import (
    button,
    delegate_definitions,
    document,
    entered_text,
    identity,
    policy,
    publish_examples,
    runtime,
)
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.domain.contracts import DelegateDefinition, NavigationEvent
from ui_flows.domain.schema import FlowDocument
from ui_flows.errors import (
    ActiveDialogError,
    DialogNotFoundError,
    FlowConflictError,
    InvalidEventError,
    InvalidFlowError,
    StaleEventError,
)


async def test_drafts_versions_and_publication_retries(session):
    services = runtime(session)
    original = document("main_menu")
    assert (await services.flows.create(original)).revision == 0
    with pytest.raises(FlowConflictError):
        await services.flows.create(original)
    first = await services.flows.publish(original.id, 0, 1)
    assert (await services.flows.publish(original.id, 0, 2)).version == first.version == 1
    changed = original.model_dump(mode="json")
    changed["nodes"][0]["text"] = [{"kind": "catalog", "key": "menu.main"}]
    assert (await services.flows.save(FlowDocument.model_validate(changed), 0)).revision == 1
    with pytest.raises(FlowConflictError):
        await services.flows.save(original, 0)
    second = await services.flows.publish(original.id, 1, 1)
    assert second.version == 2
    await services.flows.activate(original.id, 1, 2)
    assert (await services.flows.publish(original.id, 1, 1)).version == 2
    assert (await services.flows.get(original.id)).published_version == 1
    assert (await FlowRepository(session).version(original.id, 1)).document == original
    with pytest.raises(FlowConflictError):
        await services.flows.activate(original.id, 2, 2)


async def test_invalid_draft_can_be_saved_but_cannot_be_published(session):
    services = runtime(session)
    invalid = document("main_menu").model_dump(mode="json")
    invalid["nodes"][0]["buttons"][0][0]["target"] = "missing"
    await services.flows.create(FlowDocument.model_validate(invalid))
    with pytest.raises(InvalidFlowError) as caught:
        await services.flows.publish("main_menu", 0, 1)
    assert "missing_target" in {issue.code for issue in caught.value.issues}
    assert (await services.flows.get("main_menu")).published_version is None


async def test_unpublished_return_flow_is_not_accepted(session):
    services = runtime(session)
    await services.flows.create(document("student_questions"))
    with pytest.raises(InvalidFlowError) as caught:
        await services.flows.publish("student_questions", 0, 1)
    assert {issue.code for issue in caught.value.issues} == {"unpublished_return_flow"}


async def test_session_stays_on_its_version_after_publication_and_service_recreation(session, flow_user):
    services = runtime(session)
    user = identity(flow_user)
    original = document("main_menu")
    await services.flows.create(original)
    await services.flows.publish(original.id, 0, 1)
    started = await services.dialogs.start(original.id, user, 100)
    with pytest.raises(ActiveDialogError):
        await services.dialogs.start(original.id, user, 101)
    changed = original.model_dump(mode="json")
    changed["nodes"][1]["text"] = [{"kind": "catalog", "key": "menu.main"}]
    await services.flows.save(FlowDocument.model_validate(changed), 0)
    await services.flows.publish(original.id, 1, 1)
    recreated = runtime(session)
    state = await recreated.dialogs.get(started.state.id, user)
    result = await recreated.dialogs.handle(button(state, 102, "study"), user)
    assert result.state.flow_version == 1
    assert result.node.text[0].key == "menu.study"
    assert (await recreated.dialogs.start(original.id, user, 100)).outcome == "duplicate"


async def test_event_revision_identity_and_hidden_buttons_are_enforced(session, flow_user):
    services = runtime(session, runtime_policy=policy(eders_enabled=False))
    user = identity(flow_user)
    await services.flows.create(document("main_menu"))
    await services.flows.publish("main_menu", 0, 1)
    started = await services.dialogs.start("main_menu", user, 110)
    event = button(started.state, 111, "study")
    result = await services.dialogs.handle(event, user)
    assert (await services.dialogs.handle(event, user)).outcome == "duplicate"
    with pytest.raises(StaleEventError):
        await services.dialogs.handle(button(started.state, 112, "study"), user)
    with pytest.raises(InvalidEventError):
        await services.dialogs.handle(button(result.state, 113, "week"), user)
    with pytest.raises(InvalidEventError):
        await services.dialogs.handle(event.model_copy(update={"user_id": 1}), user)
    with pytest.raises(DialogNotFoundError):
        await services.dialogs.get(started.state.id, replace(user, id=1, chat_id=1))
    assert (await services.dialogs.get(result.state.id, user)).node_id == "study"
    assert await session.scalar(select(func.count()).select_from(UiFlowEvent)) == 2


@pytest.mark.parametrize("has_questions, found, beta", [(False, None, False), (True, False, True), (True, True, True)])
async def test_survey_branches_persist_only_at_completion(session, flow_user, has_questions, found, beta):
    services = runtime(session)
    await publish_examples(services)
    user = identity(flow_user)
    result = await services.dialogs.start("student_questions", user, 200)
    counter = 200

    async def click(button_id):
        nonlocal counter, result
        counter += 1
        result = await services.dialogs.handle(button(result.state, counter, button_id), user)

    async def enter(text):
        nonlocal counter, result
        counter += 1
        result = await services.dialogs.handle(entered_text(result.state, counter, text), user)

    assert result.state.node_id == "course"
    await click("year_1")
    await click("yes" if has_questions else "no")
    if has_questions:
        invalid = await services.dialogs.handle(entered_text(result.state, 250, "  "), user)
        assert invalid.outcome == "invalid_input" and invalid.state == result.state
        await enter("  My question  ")
        await click("yes" if found else "no")
        if found:
            await enter("Library")
    assert not await services.survey.has_submitted(user.id)
    await click("yes" if beta else "no")
    assert result.state.status == "completed"
    assert result.state.node_id == ("thanks_beta" if beta else "thanks")
    response = await session.get(StudentQuestionsResponse, user.id)
    assert response.had_questions is has_questions and response.wants_beta is beta
    assert response.questions == ("My question" if has_questions else None)
    assert response.answer_sources == ("Library" if found else None)
    assert "My question" not in repr(result.state)
    assert set(UiFlowEvent.__table__.columns.keys()).isdisjoint({"text", "data", "answers"})


async def test_cancel_after_confirming_replacement_preserves_previous_response(session, flow_user):
    services = runtime(session)
    await publish_examples(services)
    user = identity(flow_user)
    result = await services.dialogs.start("student_questions", user, 300)
    for update_id, button_id in [(301, "year_1"), (302, "no"), (303, "no")]:
        result = await services.dialogs.handle(button(result.state, update_id, button_id), user)
    previous = await session.get(StudentQuestionsResponse, user.id)
    submitted_at = previous.submitted_at
    result = await services.dialogs.start("student_questions", user, 304)
    assert result.state.node_id == "overwrite"
    result = await services.dialogs.handle(button(result.state, 305, "replace"), user)
    result = await services.dialogs.handle(button(result.state, 306, "cancel"), user)
    assert result.state.status == "cancelled"
    await session.refresh(previous)
    assert previous.course == "1" and previous.submitted_at == submitted_at


async def test_replacement_is_saved_only_after_the_new_form_finishes(session, flow_user):
    services = runtime(session)
    await publish_examples(services)
    user = identity(flow_user)
    result = await services.dialogs.start("student_questions", user, 320)
    for update_id, button_id in [(321, "year_1"), (322, "no"), (323, "no")]:
        result = await services.dialogs.handle(button(result.state, update_id, button_id), user)
    result = await services.dialogs.start("student_questions", user, 324)
    assert result.state.node_id == "overwrite"
    for update_id, button_id in [(325, "replace"), (326, "year_3"), (327, "no")]:
        result = await services.dialogs.handle(button(result.state, update_id, button_id), user)
    previous = await session.get(StudentQuestionsResponse, user.id, populate_existing=True)
    assert previous.course == "1"
    await services.dialogs.handle(button(result.state, 328, "yes"), user)
    await session.refresh(previous)
    assert previous.course == "3" and previous.wants_beta is True


async def test_delegate_write_and_transition_rollback_even_when_exception_is_caught(session, flow_user):
    base = runtime(session)
    adapters = SurveyDelegates(base.survey)

    async def write_then_fail(context, arguments):
        await adapters.submit(context, arguments)
        raise RuntimeError("delegate failed after write")

    definitions = [DelegateDefinition.model_validate(item) for item in delegate_definitions()]
    registry = DelegateRegistry(
        [DelegateBinding(definitions[0], adapters.has_submitted), DelegateBinding(definitions[1], write_then_fail)]
    )
    services = runtime(session, registry=registry)
    await publish_examples(services)
    user = identity(flow_user)
    result = await services.dialogs.start("student_questions", user, 400)
    result = await services.dialogs.handle(button(result.state, 401, "year_1"), user)
    result = await services.dialogs.handle(button(result.state, 402, "no"), user)
    previous = result.state
    with pytest.raises(RuntimeError, match="after write"):
        await services.dialogs.handle(button(previous, 403, "yes"), user)
    assert not await services.survey.has_submitted(user.id)
    assert await services.dialogs.get(previous.id, user) == previous
    assert await session.get(UiFlowEvent, 403) is None
    # A caught exception does not poison the enclosing request or leave half of the action committed.
    await session.commit()
    assert not await services.survey.has_submitted(user.id)


async def test_resume_never_replays_actions_and_global_cancel_releases_chat(session, flow_user):
    services = runtime(session)
    await publish_examples(services)
    user = identity(flow_user)
    result = await services.dialogs.start("student_questions", user, 500)
    event = NavigationEvent(
        kind="navigation",
        update_id=501,
        user_id=user.id,
        chat_id=user.id,
        session_id=str(result.state.id),
        expected_revision=0,
        action="resume",
    )
    resumed = await services.dialogs.handle(event, user)
    assert resumed.state == result.state and resumed.outcome == "resumed"
    cancelled = await services.dialogs.handle(event.model_copy(update={"update_id": 502, "action": "main_menu"}), user)
    assert cancelled.state.status == "cancelled"
    assert (await services.dialogs.start("main_menu", user, 503)).state.status == "waiting_button"
