from dataclasses import replace

import pytest
from sqlalchemy import func, select

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent
from manashelper.modules.ui_flows.presentation.admin_contracts import PreviewRequest, PreviewUser
from manashelper.modules.ui_flows.presentation.preview import preview
from manashelper.modules.users.infrastructure.user import User
from tests.modules.ui_flows.factories import button, entered_text, identity, policy, runtime
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.domain.schema import FlowDocument
from ui_flows.errors import FlowExecutionError, InvalidFlowError, StaleEventError


def text(value):
    return {"kind": "inline", "translations": {"en": value}}


def child_document(name="child"):
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": name,
            "entry": "ask",
            "fields": {"answer": {"type": "text"}, "private": {"type": "text"}},
            "initial_data": {"private": "child-local-only"},
            "outputs": {"answer": {"type": "text"}},
            "nodes": [
                {
                    "kind": "input",
                    "id": "ask",
                    "text": [text("Child question")],
                    "field": "answer",
                    "input_type": "text",
                    "next": "return",
                    "error": text("Try again"),
                },
                {
                    "kind": "return",
                    "id": "return",
                    "outcome": "completed",
                    "values": {"answer": {"kind": "ref", "scope": "data", "field": "answer"}},
                },
            ],
        }
    )


def parent_document(name="parent", child="child"):
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": name,
            "entry": "call",
            "fields": {"answer": {"type": "text"}, "private": {"type": "text"}},
            "initial_data": {"private": "parent-local-only"},
            "nodes": [
                {
                    "kind": "call",
                    "id": "call",
                    "flow": child,
                    "results": {"answer": "answer"},
                    "outcomes": {"completed": "show"},
                },
                {
                    "kind": "menu",
                    "id": "show",
                    "text": [text("Parent resumed")],
                    "keyboard": "inline",
                    "buttons": [[{"kind": "transition", "id": "again", "label": text("Again"), "target": "call"}]],
                },
            ],
        }
    )


async def publish(services, document):
    await services.flows.create(document)
    return await services.flows.publish(document.id, 0, 1)


async def test_call_restart_return_is_typed_isolated_and_pinned(isolated_flow_pool):
    pool = isolated_flow_pool
    async with pool.begin() as session:
        user = User(id=991401, full_name="Composition")
        session.add(user)
        await session.flush()
        who = identity(user)
        services = runtime(session)
        await publish(services, child_document())
        parent = await publish(services, parent_document())
        assert parent.dependencies == {"child": 1}
        result = await services.dialogs.start("parent", who, 170001)
        original = result.state
        assert original.flow_id == "child" and original.root_flow_id == "parent"
        assert original.data == {"private": "child-local-only"}
        assert original.frames[0].data == {"private": "parent-local-only"}
    # Reconstruct all REQUEST services from committed DB state, then change the child publication.
    async with pool.begin() as session:
        services = runtime(session)
        draft = await services.flows.get("child")
        await services.flows.save(draft.document, 0)
        await services.flows.publish("child", 1, who.id)
        persisted = await services.dialogs.get(original.id, who)
        assert persisted.frames == original.frames
        result = await services.dialogs.handle(entered_text(persisted, 170002, "checked-output"), who)
        restored = result.state
        assert restored.id == original.id and restored.flow_id == "parent" and not restored.frames
        assert restored.data == {"private": "parent-local-only", "answer": "checked-output"}
        duplicate = await services.dialogs.handle(entered_text(persisted, 170002, "do-not-apply"), who)
        assert duplicate.outcome == "duplicate" and duplicate.state == restored
        with pytest.raises(StaleEventError):
            await services.dialogs.handle(entered_text(persisted, 170003, "stale"), who)
        result = await services.dialogs.handle(button(restored, 170004, "again"), who)
        assert result.state.flow_version == 1 and result.state.flow_id == "child"
        assert result.state.frames[0].data["answer"] == "checked-output"


async def test_replace_closes_the_old_execution_and_replay_returns_the_same_target(session, flow_user):
    services = runtime(session)
    who = identity(flow_user)
    await publish(services, child_document())
    document = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "replacement",
            "entry": "replace",
            "nodes": [{"kind": "replace", "id": "replace", "flow": "child"}],
        }
    )
    await publish(services, document)
    result = await services.dialogs.start(document.id, who, 170010)
    assert result.state.flow_id == "child" and not result.state.frames
    assert result.replaced_from is not None and result.replaced_from.id != result.state.id
    source = await services.dialogs.get(result.replaced_from.id, who)
    assert source.flow_id == "replacement" and source.status == "cancelled"
    repeated = await services.dialogs.start(document.id, who, 170010)
    assert repeated.outcome == "duplicate" and repeated.state.id == result.state.id
    assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 2
    event = await session.get(UiFlowEvent, 170010)
    assert event.session_id == source.id and event.result_session_id == result.state.id


@pytest.mark.parametrize("change", ["input", "output", "outcome", "v1", "recursive"])
async def test_publication_rejects_incompatible_or_recursive_composition(session, change):
    services = runtime(session)
    await publish(services, child_document())
    document = parent_document().model_dump(mode="json")
    if change == "input":
        document["nodes"][0]["arguments"] = {"unexpected": {"kind": "literal", "value": "text"}}
    elif change == "output":
        document["fields"]["answer"]["type"] = "integer"
    elif change == "outcome":
        document["nodes"][0]["outcomes"] = {"unknown": "show"}
    elif change == "v1":
        document["schema_version"] = 1
    else:
        document["nodes"][0]["flow"] = "parent"
    await services.flows.create(FlowDocument.model_validate(document))
    with pytest.raises(InvalidFlowError):
        await services.flows.publish("parent", 0, 1)
    assert (await services.flows.get("parent")).published_version is None


async def test_automatic_budget_is_shared_across_call_boundaries_and_rolls_back(session, flow_user):
    services = runtime(session)

    # Two valid acyclic graphs each use 20 automatic conditions. Their combined chain exceeds 32.
    def conditions(target):
        return [
            {
                "kind": "condition",
                "id": f"step_{index}",
                "branches": [
                    {
                        "when": {"kind": "exists", "reference": {"kind": "ref", "scope": "user", "field": "id"}},
                        "target": f"step_{index + 1}" if index < 19 else target,
                    }
                ],
                "default": f"step_{index + 1}" if index < 19 else target,
            }
            for index in range(20)
        ]

    child = child_document().model_dump(mode="json")
    child["nodes"] = [*conditions("ask"), *child["nodes"]]
    child["entry"] = "step_0"
    await publish(services, FlowDocument.model_validate(child))
    parent = parent_document().model_dump(mode="json")
    parent["nodes"] = [*conditions("call"), *parent["nodes"]]
    parent["entry"] = "step_0"
    await publish(services, FlowDocument.model_validate(parent))
    with pytest.raises(FlowExecutionError, match="budget"):
        await services.dialogs.start("parent", identity(flow_user), 170020)
    assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 0
    assert await session.get(UiFlowEvent, 170020) is None


async def test_composed_preview_uses_a_separate_registry_and_resumes_parent(session):
    services = runtime(session)
    await publish(services, child_document())
    root = parent_document()
    request = PreviewRequest(
        document=root, user=PreviewUser(id=1, chat_id=1, locale="en", theme="basic"), eders_enabled=True
    )
    shown = await preview(request, DelegateRegistry([]), policy(), flows=services.flows)
    assert not shown.issues and shown.node_kind == "input" and shown.screen.text == "Child question"
    assert shown.position.flow_id == "child" and len(shown.position.frames) == 1
    fake_state = replace(
        # Preview has its own ephemeral identity; only the explicit event values are used.
        await _preview_state(shown),
        user_id=1,
        chat_id=1,
    )
    resumed = await preview(
        request.model_copy(
            update={"position": shown.position, "event": entered_text(fake_state, 170030, "from-preview")}
        ),
        DelegateRegistry([]),
        policy(),
        flows=services.flows,
    )
    assert not resumed.issues and resumed.node_kind == "menu" and resumed.position.flow_id == "parent"
    assert resumed.data == {"private": "parent-local-only", "answer": "from-preview"}
    assert await session.scalar(select(func.count()).select_from(UiDialogSession)) == 0


async def _preview_state(result):
    from uuid import uuid4

    from ui_flows.domain.state import DialogState

    position = result.position
    return DialogState(
        uuid4(), 1, 1, position.flow_id, position.flow_version, position.node_id, "waiting_input", 0, position.data
    )
