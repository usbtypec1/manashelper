from dataclasses import replace
from uuid import uuid4

import pytest

from manashelper.modules.ui_flows.infrastructure.deliveries import DeliveryRepository
from manashelper.modules.ui_flows.infrastructure.dialogs import DialogRepository
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError
from manashelper.modules.users.infrastructure.user import User
from tests.modules.ui_flows.factories import runtime
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.policy import FlowPolicy
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import ButtonEvent, DelegateDefinition, DelegateResult
from ui_flows.domain.schema import DataField, FlowDocument
from ui_flows.domain.state import DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import InvalidEventError, InvalidFlowError, StaleEventError


def collection_field():
    return {
        "type": "list",
        "max_items": 2,
        "items": {"type": "object", "properties": {"id": {"type": "integer"}, "label": {"type": "text"}}},
    }


def dynamic_document():
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "dynamic_actions",
            "entry": "load",
            "fields": {"rows": collection_field(), "selected": {"type": "integer", "nullable": True}},
            "initial_data": {"selected": None},
            "nodes": [
                {
                    "kind": "action",
                    "id": "load",
                    "delegate": "test.collection",
                    "results": {"rows": "rows"},
                    "outcomes": {"success": "choose"},
                },
                {
                    "kind": "menu",
                    "id": "choose",
                    "keyboard": "inline",
                    "text": [
                        {
                            "kind": "inline",
                            "translations": {"en": "First: {title}"},
                            "parameters": {
                                "title": {"kind": "ref", "scope": "data", "field": "rows", "path": [0, "label"]}
                            },
                        }
                    ],
                    "buttons": [],
                    "repeated": [
                        {
                            "source": {"kind": "ref", "scope": "data", "field": "rows"},
                            "buttons": [
                                {
                                    "kind": "transition",
                                    "id": "choose_item",
                                    "target": "done",
                                    "label": {
                                        "kind": "inline",
                                        "translations": {"en": "{title}"},
                                        "parameters": {"title": {"kind": "ref", "scope": "item", "field": "label"}},
                                    },
                                    "assignments": {"selected": {"kind": "ref", "scope": "item", "field": "id"}},
                                }
                            ],
                        }
                    ],
                },
                {"kind": "end", "id": "done", "status": "completed", "text": []},
            ],
        }
    )


async def test_saved_dynamic_callback_keeps_its_item_after_upstream_reordering_and_expires_on_revision(
    isolated_flow_pool,
):
    pool = isolated_flow_pool
    user = RuntimeUser(991_771, 991_771)
    rows = [{"id": 17, "label": "<First & chosen>"}, {"id": 24, "label": "Second"}]
    calls = []

    async def load(context, arguments):
        calls.append(context.event_id)
        return DelegateResult("success", {"rows": [dict(item) for item in rows]})

    registry = DelegateRegistry(
        [
            DelegateBinding(
                DelegateDefinition.model_validate(
                    {
                        "id": "test.collection",
                        "effect": "read",
                        "outputs": {"rows": collection_field()},
                        "outcomes": ["success"],
                    }
                ),
                load,
            )
        ]
    )
    document = dynamic_document()
    async with pool.begin() as session:
        session.add(User(id=user.id, full_name="Dynamic actions test"))
        await session.flush()
        services = runtime(session, registry=registry)
        await services.flows.create(document)
        await services.flows.publish(document.id, 0, user.id)
        result = await services.dialogs.start(document.id, user, 7710)
        screen = FlowRenderer().render(document, result, user, {})
        assert screen.text == "First: &lt;First &amp; chosen&gt;"
        assert [button.id for row in screen.buttons for button in row] == ["r0_0_0", "r0_1_0"]
        assert screen.buttons[0][0].label == "<First & chosen>"
        snapshot = screen.buttons[0][0].snapshot
        assert snapshot.template_id == "choose_item" and snapshot.assignments == {"selected": 17}
        deliveries = ScreenDeliveryService(DeliveryRepository(session), DialogRepository(session))
        intent = await deliveries.prepare(result, screen, 7710)
        assert await deliveries.claim(intent.token) is not None
        await deliveries.acknowledge(intent.token, 37710)

    # A provider refresh changes order and content after the screen was committed.
    rows[:] = [{"id": 24, "label": "Changed second"}, {"id": 99, "label": "New first"}]
    async with pool.begin() as session:
        services = runtime(session, registry=registry)
        deliveries = ScreenDeliveryService(DeliveryRepository(session), DialogRepository(session))
        state, chosen = await deliveries.callback(intent.token, 0, 37710, user)
        assert chosen.snapshot == snapshot
        event = ButtonEvent(
            kind="button",
            update_id=7711,
            user_id=user.id,
            chat_id=user.chat_id,
            session_id=str(state.id),
            expected_revision=state.revision,
            button_id=chosen.id,
            snapshot=chosen.snapshot,
        )
        following = await services.dialogs.handle(event, user)
        assert following.state.data["selected"] == 17 and following.state.status == "completed"
        with pytest.raises(StaleEventError):
            await deliveries.callback(intent.token, 0, 37710, user)
        with pytest.raises(StaleEventError):
            await services.dialogs.handle(event.model_copy(update={"update_id": 7712}), user)
    assert calls == ["7710"]


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": 1, "label": "Same"}, {"id": 2, "label": "Same"}],
        [{"id": 1, "label": "/command"}],
    ],
)
async def test_dynamic_reply_actions_reject_ambiguous_or_command_labels(rows):
    document = dynamic_document()
    menu = document.nodes[1].model_copy(update={"keyboard": "reply"})
    state = DialogState(uuid4(), 1, 1, document.id, 1, menu.id, "waiting_button", 0, {"rows": rows, "selected": None})
    with pytest.raises(InvalidScreenError):
        FlowRenderer().render(document, ExecutionResult(state, menu, "started"), RuntimeUser(1, 1), {})


@pytest.mark.parametrize(
    "rows",
    [
        [{"id": True, "label": "Wrong strict integer"}],
        [{"id": 1, "label": "Extra", "unexpected": "value"}],
        [{"id": 1, "label": "One"}, {"id": 2, "label": "Two"}, {"id": 3, "label": "Three"}],
    ],
)
async def test_dynamic_source_checks_collection_limit_and_complete_item_shape(rows):
    document = dynamic_document()
    assert not accepts_scalar(DataField.model_validate(collection_field()), rows)
    menu = document.nodes[1]
    state = DialogState(uuid4(), 1, 1, document.id, 1, menu.id, "waiting_button", 0, {"rows": rows, "selected": None})
    with pytest.raises(InvalidScreenError):
        FlowRenderer().render(document, ExecutionResult(state, menu, "started"), RuntimeUser(1, 1), {})


async def test_interpreter_uses_checked_snapshot_values_and_rejects_tampered_transition():
    document = dynamic_document()
    menu = document.nodes[1]
    user = RuntimeUser(1, 1)
    state = DialogState(
        uuid4(),
        1,
        1,
        document.id,
        1,
        menu.id,
        "waiting_button",
        0,
        {"rows": [{"id": 17, "label": "Original"}], "selected": None},
    )
    button = FlowRenderer().render(document, ExecutionResult(state, menu, "started"), user, {}).buttons[0][0]
    event = ButtonEvent(
        kind="button",
        update_id=7720,
        user_id=1,
        chat_id=1,
        session_id=str(state.id),
        expected_revision=0,
        button_id=button.id,
        snapshot=button.snapshot,
    )
    reordered = replace(state, data={"rows": [{"id": 99, "label": "Replacement"}], "selected": None})
    result = await FlowInterpreter(DelegateRegistry()).advance(document, reordered, event, user, {})
    assert result.state.data["selected"] == 17
    forged = event.model_copy(update={"snapshot": event.snapshot.model_copy(update={"target": "choose"})})
    with pytest.raises(InvalidEventError, match="published transition"):
        await FlowInterpreter(DelegateRegistry()).advance(document, state, forged, user, {})


@pytest.mark.parametrize(
    "field,value,wrong",
    [
        (collection_field(), [{"id": 7, "label": "Expected"}], [{"id": "7", "label": "Wrong"}]),
        (
            {"type": "object", "properties": {"id": {"type": "integer"}, "enabled": {"type": "boolean"}}},
            {"id": 7, "enabled": True},
            {"id": 7},
        ),
    ],
)
async def test_structured_equality_publishes_with_its_full_shape_and_reports_invalid_values(
    session, field, value, wrong
):
    document = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "structured_equality",
            "entry": "compare",
            "fields": {"selected": field},
            "initial_data": {"selected": value},
            "nodes": [
                {
                    "kind": "condition",
                    "id": "compare",
                    "branches": [
                        {
                            "when": {
                                "kind": "compare",
                                "left": {"kind": "ref", "scope": "data", "field": "selected"},
                                "operator": "eq",
                                "right": {"kind": "literal", "value": value},
                            },
                            "target": "matched",
                        }
                    ],
                    "default": "different",
                },
                {"kind": "end", "id": "matched", "status": "completed", "text": []},
                {"kind": "end", "id": "different", "status": "completed", "text": []},
            ],
        }
    )
    services = runtime(session, registry=DelegateRegistry())
    await services.flows.create(document)
    published = await services.flows.publish(document.id, 0, 1)
    assert published.document == document
    changed = document.model_dump(mode="json")
    changed["nodes"][0]["branches"][0]["when"]["right"]["value"] = wrong
    with pytest.raises(InvalidFlowError) as error:
        FlowPolicy().validate(FlowDocument.model_validate(changed), DelegateRegistry())
    assert any(issue.code == "value_type" for issue in error.value.issues)
