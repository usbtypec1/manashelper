"""Static contract checks. Publication checks and interpretation are separate steps."""

import math
from collections import deque
from collections.abc import Iterator, Mapping, Sequence, Set
from uuid import UUID

from ui_flows.domain.contracts import ContractIssue, DelegateDefinition
from ui_flows.domain.schema import (
    ActionNode,
    CallNode,
    CatalogText,
    Compare,
    ConditionNode,
    ContractModel,
    DataField,
    DataValue,
    EndNode,
    FlowDocument,
    InputNode,
    LiteralValue,
    MenuNode,
    Node,
    ReferenceValue,
    ReplaceNode,
    ReturnNode,
    TransitionButton,
    UrlButton,
    Value,
)

USER_FIELDS = {
    "id": DataField(type="integer"),
    "chat_id": DataField(type="integer"),
    "locale": DataField(type="text"),
    "theme": DataField(type="text"),
}


def accepts_scalar(field: DataField, value: DataValue, *, depth: int = 0) -> bool:
    if depth > 8:
        return False
    if value is None:
        return field.nullable
    match field.type:
        case "text":
            return isinstance(value, str)
        case "secret":
            # A secret field contains an opaque handle, never password text.

            try:
                return isinstance(value, str) and str(UUID(value)) == value
            except ValueError:
                return False
        case "list":
            return (
                isinstance(value, list)
                and len(value) <= field.max_items
                and field.items is not None
                and all(accepts_scalar(field.items, item, depth=depth + 1) for item in value)
            )
        case "object":
            return (
                isinstance(value, dict)
                and value.keys() == field.properties.keys()
                and all(accepts_scalar(field.properties[name], item, depth=depth + 1) for name, item in value.items())
            )
        case "boolean":
            return isinstance(value, bool)
        case "integer":
            return type(value) is int
        case "number":
            return type(value) in (int, float) and (not isinstance(value, float) or math.isfinite(value))


def compatible(source: DataField, target: DataField) -> bool:
    if source.nullable and not target.nullable:
        return False
    if source.type == "integer" and target.type == "number":
        return True
    if source.type != target.type:
        return False
    if source.type == "list":
        return (
            source.max_items <= target.max_items
            and source.items is not None
            and target.items is not None
            and compatible(source.items, target.items)
        )
    if source.type == "object":
        return source.properties.keys() == target.properties.keys() and all(
            compatible(value, target.properties[name]) for name, value in source.properties.items()
        )
    return True


def reference_type(
    flow: FlowDocument,
    reference: ReferenceValue,
    capabilities: Mapping[str, DataField],
    item_fields: Mapping[str, DataField] | None = None,
) -> DataField | None:
    sources = {"data": flow.fields, "user": USER_FIELDS, "capabilities": capabilities, "item": item_fields or {}}
    current = sources[reference.scope].get(reference.field)
    for component in reference.path:
        if current is None:
            return None
        if current.type == "object" and isinstance(component, str):
            current = current.properties.get(component)
        elif current.type == "list" and type(component) is int:
            current = current.items
        else:
            return None
    return current


def sample_value(field: DataField) -> DataValue:
    if field.type == "list":
        return []
    if field.type == "object":
        return {name: sample_value(value) for name, value in field.properties.items()}
    samples: dict[str, DataValue] = {
        "text": "value",
        "integer": 1,
        "number": 1.0,
        "boolean": True,
        "secret": "00000000-0000-0000-0000-000000000000",
    }
    return samples[field.type]


def _walk(value: object, path: str, button_id: str | None = None) -> Iterator[tuple[ContractModel, str, str | None]]:
    if isinstance(value, ContractModel):
        if isinstance(value, (TransitionButton, UrlButton)):
            button_id = value.id
        yield value, path, button_id
        for name in type(value).model_fields:
            yield from _walk(getattr(value, name), f"{path}/{name}", button_id)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}/{index}", button_id)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{path}/{key}", button_id)


def _edges(node: Node) -> Iterator[tuple[str, str, str | None]]:
    if isinstance(node, ConditionNode):
        yield node.default, "/default", None
        for index, branch in enumerate(node.branches):
            yield branch.target, f"/branches/{index}/target", None
    elif isinstance(node, (ActionNode, CallNode)):
        for outcome, target in node.outcomes.items():
            yield target, f"/outcomes/{outcome}", None
    elif isinstance(node, (MenuNode, InputNode)):
        if isinstance(node, InputNode):
            yield node.next, "/next", None
        for row_index, row in enumerate(node.buttons):
            for button_index, button in enumerate(row):
                if isinstance(button, TransitionButton):
                    yield button.target, f"/buttons/{row_index}/{button_index}/target", button.id
        if isinstance(node, MenuNode):
            for group_index, group in enumerate(node.repeated):
                for button_index, button in enumerate(group.buttons):
                    if isinstance(button, TransitionButton):
                        yield button.target, f"/repeated/{group_index}/buttons/{button_index}/target", button.id


def node_targets(node: Node) -> list[str]:
    return [target for target, _, _ in _edges(node)]


def validate_flow(
    flow: FlowDocument,
    *,
    delegates: Sequence[DelegateDefinition],
    features: Set[str],
    catalog_keys: Set[str],
    capabilities: Mapping[str, DataField],
) -> list[ContractIssue]:
    """Check a parsed document against the application's explicitly supplied catalog."""
    issues: list[ContractIssue] = []
    nodes = {node.id: node for node in flow.nodes}
    definitions = {(definition.id, definition.version): definition for definition in delegates}
    item_fields: Mapping[str, DataField] = {}

    def issue(code: str, path: str, message: str, node_id: str | None = None, button_id: str | None = None) -> None:
        issues.append(ContractIssue(code=code, path=path, message=message, node_id=node_id, button_id=button_id))

    def reference_field(reference: ReferenceValue) -> DataField | None:
        return reference_type(flow, reference, capabilities, item_fields)

    def check_value(value: Value, target: DataField, path: str, node_id: str | None) -> None:
        if isinstance(value, LiteralValue):
            matches_type = accepts_scalar(target, value.value)
        else:
            source = reference_field(value)
            if source is None:
                return  # The reference itself is reported by the model walk.
            matches_type = compatible(source, target)
        if not matches_type:
            issue("value_type", path, "Value is incompatible with the destination field", node_id)

    if flow.entry not in nodes:
        issue("missing_entry", "/entry", "Entry node does not exist")
    for navigation_name, target in flow.navigation_entries.items():
        if not isinstance(nodes.get(target), MenuNode):
            issue(
                "invalid_navigation_entry",
                f"/navigation_entries/{navigation_name}",
                "Navigation entry must reference a menu",
            )
    seen = set()
    if len(set(flow.outcomes)) != len(flow.outcomes):
        issue("duplicate_outcome", "/outcomes", "Scenario outcomes must be unique")
    if flow.schema_version == 1 and (flow.inputs or flow.outputs or flow.outcomes != ["completed"]):
        issue("v2_contract", "/schema_version", "Scenario interfaces require schema version 2")
    if flow.schema_version == 1 and any(field.type in {"list", "object", "secret"} for field in flow.fields.values()):
        issue("v2_data", "/fields", "Structured and secret values require schema version 2")
    for name, parameter in flow.inputs.items():
        if flow.fields.get(name) != parameter:
            issue("scenario_input", f"/inputs/{name}", "An input must declare the same local field type")
    for index, node in enumerate(flow.nodes):
        path = f"/nodes/{index}"
        item_fields = {}
        repeated_fields: dict[str, Mapping[str, DataField]] = {}
        if isinstance(node, MenuNode) and node.repeated:
            if flow.schema_version != 2:
                issue("v2_buttons", path, "Repeated actions require schema version 2", node.id)
            for group_index, group in enumerate(node.repeated):
                declaration = reference_type(flow, group.source, capabilities)
                group_path = f"{path}/repeated/{group_index}/buttons"
                if (
                    declaration is None
                    or declaration.type != "list"
                    or declaration.items is None
                    or declaration.items.type != "object"
                ):
                    issue("button_source", group_path, "Repeated actions require a typed object collection", node.id)
                else:
                    repeated_fields[group_path] = declaration.items.properties
        if isinstance(node, (CallNode, ReturnNode, ReplaceNode)) and flow.schema_version != 2:
            issue("v2_node", path, "Composition nodes require schema version 2", node.id)
        if isinstance(node, EndNode) and flow.schema_version == 2 and (flow.outputs or node.return_flow):
            issue("v2_ending", path, "Use an explicit Return or Replace for a composed scenario", node.id)
        if isinstance(node, ReturnNode):
            if node.outcome not in flow.outcomes or node.values.keys() != flow.outputs.keys():
                issue("scenario_return", path, "Return must supply declared outputs and an outcome", node.id)
            for name, value in node.values.items():
                if name in flow.outputs:
                    check_value(value, flow.outputs[name], f"{path}/values/{name}", node.id)
        if node.id in seen:
            issue("duplicate_node", f"{path}/id", "Node IDs must be unique", node.id)
        seen.add(node.id)
        for target, suffix, edge_button_id in _edges(node):
            if target not in nodes:
                issue("missing_target", path + suffix, f"Target '{target}' does not exist", node.id, edge_button_id)
        for model, model_path, model_button_id in _walk(node, path):
            item_fields = next(
                (fields for prefix, fields in repeated_fields.items() if model_path.startswith(prefix + "/")), {}
            )
            if isinstance(model, ReferenceValue) and reference_field(model) is None:
                issue(
                    "unknown_reference",
                    model_path + "/field",
                    f"Unknown {model.scope} field '{model.field}'",
                    node.id,
                    model_button_id,
                )
            if isinstance(model, CatalogText) and model.key not in catalog_keys:
                issue(
                    "unknown_message_key",
                    model_path + "/key",
                    f"Unknown catalog key '{model.key}'",
                    node.id,
                    model_button_id,
                )
            if isinstance(model, Compare):
                left = reference_field(model.left)
                if left is not None:
                    if isinstance(model.right, list):
                        if any(not accepts_scalar(left, value) for value in model.right):
                            issue(
                                "condition_type",
                                model_path + "/right",
                                "Membership values do not match the field type",
                                node.id,
                                model_button_id,
                            )
                    else:
                        check_value(
                            model.right, left.model_copy(update={"nullable": True}), model_path + "/right", node.id
                        )
                    if model.operator in {"lt", "le", "gt", "ge"} and (
                        left.type not in {"integer", "number"}
                        or (isinstance(model.right, LiteralValue) and model.right.value is None)
                    ):
                        issue(
                            "condition_type", model_path, "Ordering requires numeric operands", node.id, model_button_id
                        )
        if isinstance(node, (MenuNode, InputNode)):
            item_fields = {}
            if flow.schema_version != 2 and (
                node.media is not None or node.messages or node.message_source is not None
            ):
                issue("v2_screen", path, "Rich screens require schema version 2", node.id)
            if node.media is not None:
                media = reference_type(flow, node.media, capabilities)
                media_item = media.items if media is not None and media.type == "list" else None
                if (
                    media is None
                    or media.type != "list"
                    or media.nullable
                    or media.max_items > 10
                    or media_item is None
                    or media_item.type != "object"
                    or media_item.nullable
                    or any(
                        name not in media_item.properties
                        or not compatible(media_item.properties[name], DataField(type="text"))
                        for name in ("type", "file_id")
                    )
                    or (
                        "caption" in media_item.properties
                        and not compatible(media_item.properties["caption"], DataField(type="text", nullable=True))
                    )
                ):
                    issue(
                        "screen_media",
                        f"{path}/media",
                        "Media requires at most ten objects with text type/file_id and an optional text caption",
                        node.id,
                    )
            if node.message_source is not None:
                messages = reference_type(flow, node.message_source, capabilities)
                if messages is None or not compatible(
                    messages, DataField(type="list", items=DataField(type="text"), max_items=20)
                ):
                    issue(
                        "message_source",
                        f"{path}/message_source",
                        "Message source requires at most twenty text chunks",
                        node.id,
                    )
                elif len(node.messages) + messages.max_items > 20:
                    issue(
                        "screen_messages", path, "Authored and sourced messages must fit within twenty chunks", node.id
                    )
            button_ids: set[str] = set()
            for row_index, row in enumerate(node.buttons):
                for button_index, button in enumerate(row):
                    button_path = f"{path}/buttons/{row_index}/{button_index}"
                    if button.id in button_ids:
                        issue(
                            "duplicate_button", button_path, "Button IDs must be unique in a screen", node.id, button.id
                        )
                    button_ids.add(button.id)
                    if isinstance(node, MenuNode) and node.keyboard == "reply" and isinstance(button, UrlButton):
                        issue(
                            "reply_url", button_path, "Reply keyboards cannot contain URL buttons", node.id, button.id
                        )
                    if isinstance(button, TransitionButton):
                        for field, value in button.assignments.items():
                            if field not in flow.fields:
                                issue("unknown_field", button_path, f"Undeclared assignment field '{field}'", node.id)
                            else:
                                check_value(value, flow.fields[field], button_path, node.id)
            if isinstance(node, MenuNode):
                for group_index, group in enumerate(node.repeated):
                    button_path = f"{path}/repeated/{group_index}/buttons"
                    item_fields = repeated_fields.get(button_path, {})
                    for button in group.buttons:
                        if button.id in button_ids:
                            issue(
                                "duplicate_button",
                                button_path,
                                "Action template IDs must be unique",
                                node.id,
                                button.id,
                            )
                        button_ids.add(button.id)
                        if node.keyboard == "reply" and isinstance(button, UrlButton):
                            issue(
                                "reply_url",
                                button_path,
                                "Reply keyboards cannot contain URL buttons",
                                node.id,
                                button.id,
                            )
                        if isinstance(button, TransitionButton):
                            for name, value in button.assignments.items():
                                if name not in flow.fields:
                                    issue("unknown_field", button_path, "Assignment field is undeclared", node.id)
                                else:
                                    check_value(value, flow.fields[name], button_path, node.id)
            item_fields = {}
        if isinstance(node, InputNode):
            input_field = flow.fields.get(node.field)
            if input_field is None:
                issue("unknown_field", f"{path}/field", "Input field is not declared", node.id)
            elif node.input_type != "choice" and input_field.type != {
                "contact": "text",
                "media": "list" if node.multiple else "object",
            }.get(node.input_type, node.input_type):
                issue("input_type", f"{path}/input_type", "Input and field types differ", node.id)
            elif any(not accepts_scalar(input_field, value) for value in node.choices):
                issue("input_type", f"{path}/choices", "Choices and field types differ", node.id)
        if isinstance(node, EndNode) and node.feature is not None and node.feature not in features:
            issue("unknown_feature", f"{path}/feature", "Feature entry point is not registered", node.id)
        if isinstance(node, ActionNode):
            definition = definitions.get((node.delegate, node.contract_version))
            if definition is None:
                issue("unknown_delegate", f"{path}/delegate", "Delegate contract is not registered", node.id)
                continue
            if definition.effect == "external" and (flow.schema_version != 2 or not node.waiting_text):
                issue("external_action", path, "External actions require version 2 and a waiting message", node.id)
            required = {name for name, parameter in definition.inputs.items() if parameter.required}
            if not required <= node.arguments.keys() or not node.arguments.keys() <= definition.inputs.keys():
                issue("delegate_arguments", f"{path}/arguments", "Delegate inputs are missing or unknown", node.id)
            for name, value in node.arguments.items():
                if name in definition.inputs:
                    check_value(value, definition.inputs[name], f"{path}/arguments/{name}", node.id)
            if set(node.outcomes) != set(definition.outcomes):
                issue(
                    "delegate_outcomes", f"{path}/outcomes", "Every declared outcome needs exactly one route", node.id
                )
            for name, field_name in node.results.items():
                if name not in definition.outputs or field_name not in flow.fields:
                    issue("delegate_results", f"{path}/results", "Output or destination field is unknown", node.id)
                else:
                    source = definition.outputs[name]
                    destination = flow.fields[field_name]
                    if not compatible(source, destination):
                        issue("delegate_results", f"{path}/results/{name}", "Output field types differ", node.id)

    for field, initial_value in flow.initial_data.items():
        if field not in flow.fields or not accepts_scalar(flow.fields[field], initial_value):
            issue("initial_data", f"/initial_data/{field}", "Initial value is undeclared or has the wrong type")
    for node_id in flow.layout:
        if node_id not in nodes:
            issue("unknown_layout_node", f"/layout/{node_id}", "Layout references an unknown node")

    reachable: set[str] = set()
    pending = [flow.entry]
    while pending:
        node_id = pending.pop()
        if node_id in reachable or node_id not in nodes:
            continue
        reachable.add(node_id)
        pending.extend(node_targets(nodes[node_id]))
    for node_id in nodes.keys() - reachable:
        issue("unreachable_node", "/nodes", "Node cannot be reached from the entry", node_id)

    # A Call can suspend on a child screen. The shared runtime budget bounds zero-wait call loops.
    automatic = {node.id: node for node in flow.nodes if isinstance(node, (ConditionNode, ActionNode))}
    incoming = dict.fromkeys(automatic, 0)
    for node in automatic.values():
        for target in node_targets(node):
            if target in incoming:
                incoming[target] += 1
    ready = deque(node_id for node_id, count in incoming.items() if count == 0)
    while ready:
        for target in node_targets(automatic[ready.popleft()]):
            if target in incoming:
                incoming[target] -= 1
                if incoming[target] == 0:
                    ready.append(target)
    if any(incoming.values()):
        issue("automatic_cycle", "/nodes", "Automatic steps must reach a wait or end without cycling")
    return issues
