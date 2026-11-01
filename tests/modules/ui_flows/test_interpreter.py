from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from tests.modules.ui_flows.factories import button, document, entered_text
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.application.interpreter import EvaluationContext, FlowInterpreter
from ui_flows.domain.contracts import DelegateContext, DelegateDefinition, DelegateResult
from ui_flows.domain.schema import Compare, FlowDocument, ReferenceValue
from ui_flows.domain.state import DialogState, RuntimeUser
from ui_flows.errors import FlowExecutionError, InvalidEventError


async def test_menu_transition_does_not_mutate_the_previous_snapshot():
    flow = document("main_menu")
    interpreter = FlowInterpreter(DelegateRegistry())
    user = RuntimeUser(10, 10)
    state = DialogState(uuid4(), 10, 10, flow.id, 1, flow.entry, "running", 0, {})
    state = await interpreter.settle(flow, state, user, {"eders_enabled": False}, "1")
    result = await interpreter.advance(flow, state, button(state, 2, "study"), user, {"eders_enabled": False})
    assert result.state.node_id == "study"
    assert result.state.revision == 1
    assert state.node_id == "main" and state.revision == 0
    with pytest.raises(InvalidEventError):
        await interpreter.advance(flow, result.state, button(result.state, 3, "week"), user, {"eders_enabled": False})


@pytest.mark.parametrize("value, expected", [(False, False), (0, False), (1, True), (None, False)])
def test_boolean_values_are_not_numeric_conditions(value, expected):
    flow = document("student_questions")
    context = EvaluationContext(flow, {"course": value}, RuntimeUser(1, 1), {})
    condition = Compare.model_validate(
        {
            "kind": "compare",
            "left": {"kind": "ref", "scope": "data", "field": "course"},
            "operator": "eq",
            "right": {"kind": "literal", "value": 1},
        }
    )
    assert context.matches(condition) is expected


@pytest.mark.parametrize("length, succeeds", [(32, True), (33, False)])
async def test_automatic_step_budget_counts_actions_not_the_final_wait(length, succeeds):
    condition = {"kind": "exists", "reference": {"kind": "ref", "scope": "user", "field": "id"}}
    nodes = [
        {
            "kind": "condition",
            "id": f"step_{index}",
            "branches": [{"when": condition, "target": f"step_{index + 1}"}],
            "default": f"step_{index + 1}",
        }
        for index in range(length)
    ]
    nodes.append({"kind": "end", "id": f"step_{length}", "status": "completed"})
    flow = FlowDocument.model_validate({"schema_version": 1, "id": "budget", "entry": "step_0", "nodes": nodes})
    state = DialogState(uuid4(), 1, 1, "budget", 1, "step_0", "running", 0, {})
    interpreter = FlowInterpreter(DelegateRegistry())
    if succeeds:
        assert (await interpreter.settle(flow, state, RuntimeUser(1, 1), {}, "1")).status == "completed"
    else:
        with pytest.raises(FlowExecutionError, match="budget"):
            await interpreter.settle(flow, state, RuntimeUser(1, 1), {}, "1")


@pytest.mark.parametrize(
    "input_type, field_type, text, choices, expected, valid",
    [
        ("integer", "integer", " 12 ", [], 12, True),
        ("integer", "integer", "1.5", [], None, False),
        ("integer", "integer", "true", [], None, False),
        ("choice", "boolean", "false", [True, False], False, True),
        ("choice", "text", "other", ["yes", "no"], None, False),
        ("choice", "number", "nan", [1.0], None, False),
        ("choice", "integer", "null", [None, 1], None, True),
    ],
)
async def test_inputs_are_parsed_explicitly(input_type, field_type, text, choices, expected, valid):
    flow = FlowDocument.model_validate(
        {
            "schema_version": 1,
            "id": "input",
            "entry": "ask",
            "fields": {"answer": {"type": field_type, "nullable": True}},
            "nodes": [
                {
                    "kind": "input",
                    "id": "ask",
                    "text": [{"kind": "inline", "translations": {"en": "Answer"}}],
                    "field": "answer",
                    "input_type": input_type,
                    "next": "done",
                    "choices": choices,
                    "error": {"kind": "inline", "translations": {"en": "Invalid"}},
                },
                {"kind": "end", "id": "done", "status": "completed"},
            ],
        }
    )
    state = DialogState(uuid4(), 1, 1, flow.id, 1, "ask", "waiting_input", 0, {})
    result = await FlowInterpreter(DelegateRegistry()).advance(
        flow, state, entered_text(state, 1, text), RuntimeUser(1, 1), {}
    )
    assert (result.outcome != "invalid_input") is valid
    assert result.state.data.get("answer") == expected
    assert state.data == {}


async def test_delegate_registry_checks_inputs_and_outputs_before_using_results():
    definition = DelegateDefinition.model_validate(
        {
            "id": "test.read",
            "effect": "read",
            "inputs": {"id": {"type": "integer"}},
            "outputs": {"answer": {"type": "boolean"}},
            "outcomes": ["success"],
        }
    )
    handler = AsyncMock(return_value=DelegateResult("success", {"answer": "true"}))
    registry = DelegateRegistry([DelegateBinding(definition, handler)])
    context = DelegateContext(1, 1, "session", "event")
    with pytest.raises(FlowExecutionError):
        await registry.execute("test.read", 1, context, {"id": True})
    handler.assert_not_awaited()
    with pytest.raises(FlowExecutionError):
        await registry.execute("test.read", 1, context, {"id": 1})
    with pytest.raises(ValueError):
        DelegateRegistry([DelegateBinding(definition, handler), DelegateBinding(definition, handler)])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
async def test_delegate_cannot_return_non_finite_json_numbers(value):
    definition = DelegateDefinition.model_validate(
        {"id": "test.number", "effect": "read", "outputs": {"answer": {"type": "number"}}, "outcomes": ["success"]}
    )
    registry = DelegateRegistry(
        [DelegateBinding(definition, AsyncMock(return_value=DelegateResult("success", {"answer": value})))]
    )
    with pytest.raises(FlowExecutionError):
        await registry.execute("test.number", 1, DelegateContext(1, 1, "session", "event"), {})


def test_nullable_missing_reference_and_exists_are_distinct_from_required_values():
    flow = document("student_questions")
    context = EvaluationContext(flow, {}, RuntimeUser(1, 1), {})
    assert context.resolve(ReferenceValue(kind="ref", scope="data", field="questions")) is None
    with pytest.raises(FlowExecutionError):
        context.resolve(ReferenceValue(kind="ref", scope="data", field="course"))
