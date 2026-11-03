"""Typed scenario boundaries, independent of transport and persistence."""

from collections.abc import Mapping

from ui_flows.application.validation import accepts_scalar, compatible, reference_type
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.schema import CallNode, DataField, FlowDocument, LiteralValue, ReplaceNode, Value

MAX_CALL_DEPTH = 16


def argument_matches(
    document: FlowDocument, value: Value, target: DataField, capabilities: Mapping[str, DataField]
) -> bool:
    if isinstance(value, LiteralValue):
        return accepts_scalar(target, value.value)
    source = reference_type(document, value, capabilities)
    return source is not None and compatible(source, target)


def validate_boundary(
    parent: FlowDocument, node: CallNode | ReplaceNode, child: FlowDocument, capabilities: Mapping[str, DataField]
) -> list[ContractIssue]:
    messages = []
    if child.schema_version != 2:
        messages.append("A composed target must declare a version 2 interface")
    if node.arguments.keys() != child.inputs.keys():
        messages.append("Scenario arguments must match the declared inputs")
    for name, value in node.arguments.items():
        if name in child.inputs and not argument_matches(parent, value, child.inputs[name], capabilities):
            messages.append("Scenario argument types differ")
    if isinstance(node, CallNode):
        if set(node.outcomes) != set(child.outcomes):
            messages.append("Every child outcome needs exactly one continuation")
        for name, destination in node.results.items():
            if name not in child.outputs or destination not in parent.fields:
                messages.append("Scenario output or destination is undeclared")
            elif not compatible(child.outputs[name], parent.fields[destination]):
                messages.append("Scenario output types differ")
    index = next(index for index, item in enumerate(parent.nodes) if item.id == node.id)
    return [
        ContractIssue(code="scenario_contract", path=f"/nodes/{index}", message=message, node_id=node.id)
        for message in messages
    ]
