"""In-memory execution between waits; persistence and transactions belong to the use case."""

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace

from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import (
    ButtonEvent,
    ContactEvent,
    DelegateContext,
    DelegateDefinition,
    DelegateResult,
    FlowEvent,
    InputEvent,
    MediaEvent,
    NavigationEvent,
    SecretEvent,
    SessionStatus,
)
from ui_flows.domain.schema import (
    CallNode,
    ConditionGroup,
    ConditionNode,
    DataValue,
    EndNode,
    Exists,
    FlowDocument,
    InputNode,
    LiteralValue,
    MenuNode,
    Predicate,
    ReplaceNode,
    ReturnNode,
    Scalar,
    TransitionButton,
    Value,
)
from ui_flows.domain.state import ACTIVE_STATUSES, DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import FlowExecutionError, InvalidEventError


def _equal(left: DataValue, right: DataValue) -> bool:
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


class EvaluationContext:
    def __init__(
        self,
        document: FlowDocument,
        data: dict[str, DataValue],
        user: RuntimeUser,
        capabilities: Mapping[str, Scalar],
        *,
        item: Mapping[str, DataValue] | None = None,
    ) -> None:
        self.document = document
        self.data = data
        self.sources: dict[str, Mapping[str, DataValue]] = {
            "data": data,
            "user": {"id": user.id, "chat_id": user.chat_id, "locale": user.locale, "theme": user.theme},
            "capabilities": capabilities,
            "item": item or {},
        }

    def resolve(self, value: Value, *, missing_ok: bool = False) -> DataValue:
        if isinstance(value, LiteralValue):
            return value.value
        source = self.sources[value.scope]
        if value.field in source:
            resolved = source[value.field]
            for component in value.path:
                if isinstance(resolved, dict) and isinstance(component, str) and component in resolved:
                    resolved = resolved[component]
                    continue
                if isinstance(resolved, list) and type(component) is int and 0 <= component < len(resolved):
                    resolved = resolved[component]
                    continue
                if missing_ok:
                    return None
                raise FlowExecutionError("Required structured value is unavailable")
            return resolved
        declaration = self.document.fields.get(value.field) if value.scope == "data" else None
        if missing_ok or (declaration is not None and declaration.nullable):
            return None
        raise FlowExecutionError("Required context value is unavailable")

    def matches(self, condition: Predicate) -> bool:
        if isinstance(condition, ConditionGroup):
            results = (self.matches(child) for child in condition.conditions)
            return all(results) if condition.kind == "all" else any(results)
        if isinstance(condition, Exists):
            return self.resolve(condition.reference, missing_ok=True) is not None
        left = self.resolve(condition.left)
        if isinstance(condition.right, list):
            return any(_equal(left, item) for item in condition.right)
        right = self.resolve(condition.right)
        if condition.operator == "eq":
            return _equal(left, right)
        if condition.operator == "ne":
            return not _equal(left, right)
        if type(left) not in (int, float) or type(right) not in (int, float):
            return False
        # bool is deliberately excluded; values are narrowed independently for mypy.
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return False
        match condition.operator:
            case "lt":
                return left < right
            case "le":
                return left <= right
            case "gt":
                return left > right
            case "ge":
                return left >= right
        raise FlowExecutionError("Unsupported condition operator")

    def assign(self, values: Mapping[str, Value]) -> None:
        # Resolve all bindings before assigning, so iteration order cannot change semantics.
        resolved = {name: self.resolve(value) for name, value in values.items()}
        for name, value in resolved.items():
            declaration = self.document.fields.get(name)
            if declaration is None or not accepts_scalar(declaration, value):
                raise FlowExecutionError("Assignment does not match the declared field")
        self.data.update(resolved)


@dataclass(slots=True)
class StepBudget:
    remaining: int = 32

    def consume(self) -> None:
        if self.remaining <= 0:
            raise FlowExecutionError("Automatic step budget exhausted")
        self.remaining -= 1


class FlowInterpreter:
    def __init__(self, registry: DelegateRegistry) -> None:
        self._registry = registry

    async def settle(
        self,
        document: FlowDocument,
        state: DialogState,
        user: RuntimeUser,
        capabilities: Mapping[str, Scalar],
        event_id: str,
        budget: StepBudget | None = None,
    ) -> DialogState:
        budget = budget or StepBudget()
        context = EvaluationContext(document, dict(state.data), user, capabilities)
        nodes = {node.id: node for node in document.nodes}
        node_id = state.node_id
        while True:
            node = nodes.get(node_id)
            if node is None:
                raise FlowExecutionError("Current node is unavailable")
            if isinstance(node, (MenuNode, InputNode)):
                status: SessionStatus = "waiting_button" if isinstance(node, MenuNode) else "waiting_input"
                return replace(state, node_id=node_id, data=context.data, status=status)
            if isinstance(node, EndNode):
                return replace(state, node_id=node_id, data=context.data, status=node.status)
            if isinstance(node, (CallNode, ReturnNode, ReplaceNode)):
                return replace(state, node_id=node_id, data=context.data, status="running")
            budget.consume()
            if isinstance(node, ConditionNode):
                node_id = next(
                    (branch.target for branch in node.branches if context.matches(branch.when)), node.default
                )
                continue
            if self._registry.definition(node.delegate, node.contract_version).effect == "external":
                return replace(state, node_id=node_id, data=context.data, status="waiting_effect")
            result = await self._registry.execute(
                node.delegate,
                node.contract_version,
                DelegateContext(user.id, user.chat_id, str(state.id), event_id, locale=user.locale, theme=user.theme),
                {name: context.resolve(value) for name, value in node.arguments.items()},
            )
            for name, destination in node.results.items():
                if name not in result.values:
                    raise FlowExecutionError("A bound delegate output is missing")
                value = result.values[name]
                if destination not in document.fields or not accepts_scalar(document.fields[destination], value):
                    raise FlowExecutionError("Delegate output cannot be assigned to the destination")
                context.data[destination] = value
            node_id = node.outcomes[result.outcome]

    async def advance(
        self,
        document: FlowDocument,
        state: DialogState,
        event: FlowEvent,
        user: RuntimeUser,
        capabilities: Mapping[str, Scalar],
        budget: StepBudget | None = None,
    ) -> ExecutionResult:
        nodes = {node.id: node for node in document.nodes}
        node = nodes[state.node_id]
        if isinstance(event, NavigationEvent) and event.action == "resume":
            return ExecutionResult(state, node, "resumed")
        if state.status not in ACTIVE_STATUSES:
            raise InvalidEventError("The dialog has already ended")
        if isinstance(event, NavigationEvent):
            return ExecutionResult(replace(state, status="cancelled", revision=state.revision + 1), node, "cancelled")
        context = EvaluationContext(document, dict(state.data), user, capabilities)
        if isinstance(event, ButtonEvent) and isinstance(node, (MenuNode, InputNode)):
            candidates = [button for row in node.buttons for button in row]
            if isinstance(node, MenuNode) and event.snapshot is not None:
                candidates.extend(button for group in node.repeated for button in group.buttons)
            template_id = event.snapshot.template_id if event.snapshot is not None else event.button_id
            button = next((button for button in candidates if button.id == template_id), None)
            if event.snapshot is not None:
                context = EvaluationContext(document, dict(state.data), user, capabilities, item=event.snapshot.item)
            if not isinstance(button, TransitionButton) or (
                button.when is not None and not context.matches(button.when)
            ):
                raise InvalidEventError("The button is not available on the current screen")
            if event.snapshot is not None:
                if (
                    event.snapshot.target != button.target
                    or event.snapshot.assignments.keys() != button.assignments.keys()
                ):
                    raise InvalidEventError("Saved action does not match its published transition")
                context.assign(
                    {
                        name: LiteralValue(kind="literal", value=value)
                        for name, value in event.snapshot.assignments.items()
                    }
                )
            else:
                context.assign(button.assignments)
            target = button.target
        elif isinstance(event, InputEvent) and isinstance(node, InputNode):
            if node.input_type in {"secret", "media"}:
                raise InvalidEventError("This input requires its typed transport event")
            valid, value = self._parse_input(node, document, event.text)
            if not valid:
                return ExecutionResult(state, node, "invalid_input")
            context.data[node.field] = value
            target = node.next
        elif isinstance(event, SecretEvent) and isinstance(node, InputNode) and node.input_type == "secret":
            if not accepts_scalar(document.fields[node.field], event.handle):
                raise InvalidEventError("Secret handle is invalid")
            context.data[node.field] = event.handle
            target = node.next
        elif isinstance(event, ContactEvent) and isinstance(node, InputNode) and node.input_type == "contact":
            if event.owner_id != user.id:
                return ExecutionResult(state, node, "invalid_input")
            context.data[node.field] = event.phone
            target = node.next
        elif isinstance(event, MediaEvent) and isinstance(node, InputNode) and node.input_type == "media":
            item: dict[str, DataValue] = {
                "message_id": event.message_id,
                "type": event.media_type,
                "file_id": event.file_id,
                "media_group_id": event.media_group_id,
                "caption": event.caption,
            }
            if node.multiple:
                previous = context.data.get(node.field, [])
                if not isinstance(previous, list):
                    raise FlowExecutionError("Media collection has invalid state")
                if any(isinstance(saved, dict) and saved.get("message_id") == event.message_id for saved in previous):
                    return ExecutionResult(state, node, "duplicate")
                collected: DataValue = [*previous, item]
            else:
                collected = item
            if not accepts_scalar(document.fields[node.field], collected):
                return ExecutionResult(state, node, "invalid_input")
            context.data[node.field] = collected
            target = node.id if node.multiple else node.next
        else:
            raise InvalidEventError("The event is not accepted by the current step")
        advanced = await self.settle(
            document,
            replace(state, node_id=target, revision=state.revision + 1, data=context.data),
            user,
            capabilities,
            str(event.update_id),
            budget,
        )
        return ExecutionResult(advanced, nodes[advanced.node_id], "advanced")

    @staticmethod
    def _parse_input(node: InputNode, document: FlowDocument, text: str) -> tuple[bool, Scalar]:
        text = text.strip()
        if not node.min_length <= len(text) <= node.max_length:
            return False, None
        field = document.fields[node.field]
        if node.input_type == "choice" and field.nullable and text == "null" and None in node.choices:
            return True, None
        value: Scalar
        try:
            if field.type == "text":
                value = text
            elif field.type == "integer":
                if re.fullmatch(r"[+-]?[0-9]+", text) is None:
                    return False, None
                value = int(text)
                if node.minimum is not None and value < node.minimum:
                    return False, None
                if node.maximum is not None and value > node.maximum:
                    return False, None
            elif field.type == "number":
                value = float(text)
                if not math.isfinite(value):
                    return False, None
            elif text in {"true", "false"}:
                value = text == "true"
            else:
                return False, None
        except ValueError:
            return False, None
        if node.input_type == "choice" and not any(_equal(value, choice) for choice in node.choices):
            return False, None
        return True, value

    def definition(self, delegate_id: str, version: int) -> DelegateDefinition:
        return self._registry.definition(delegate_id, version)

    def validate_result(self, delegate_id: str, version: int, result: DelegateResult) -> DelegateResult:
        return self._registry.validate_result(delegate_id, version, result)

    def validate_arguments(self, delegate_id: str, version: int, arguments: Mapping[str, DataValue]) -> None:
        self._registry.validate_arguments(delegate_id, version, arguments)
