from collections.abc import Mapping
from dataclasses import replace
from uuid import uuid4

from manashelper.modules.ui_flows.presentation.admin_contracts import (
    PreviewButton,
    PreviewDelegateResult,
    PreviewRequest,
    PreviewResult,
    PreviewScreen,
)
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.policy import FlowPolicy
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import ContractIssue, DelegateContext, DelegateResult
from ui_flows.domain.schema import Scalar
from ui_flows.domain.state import DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import FlowExecutionError, InvalidEventError, InvalidFlowError


class _Stub:
    def __init__(self, result: PreviewDelegateResult | None) -> None:
        self._result = result

    async def __call__(self, context: DelegateContext, arguments: Mapping[str, Scalar]) -> DelegateResult:
        if self._result is None:
            raise FlowExecutionError("A preview delegate result is required")
        return DelegateResult(self._result.outcome, self._result.values)


async def preview(request: PreviewRequest, definitions: DelegateRegistry, policy: FlowPolicy) -> PreviewResult:
    document = request.document
    node_id = request.node_id or document.entry
    data = {**document.initial_data, **request.data}

    def failed(issues: list[ContractIssue]) -> PreviewResult:
        return PreviewResult(node_id=node_id, data=data, screen=None, issues=issues)

    try:
        policy.validate(document, definitions)
    except InvalidFlowError as error:
        return failed(error.issues)
    nodes = {node.id: node for node in document.nodes}
    if node_id not in nodes:
        return failed([ContractIssue(code="unknown_node", path="/node_id", message="Node does not exist")])
    if (
        request.user.id <= 0
        or request.user.chat_id != request.user.id
        or any(
            name not in document.fields or not accepts_scalar(document.fields[name], value)
            for name, value in data.items()
        )
    ):
        return failed([ContractIssue(code="invalid_context", path="/data", message="Preview context is invalid")])
    user = RuntimeUser(request.user.id, request.user.chat_id, request.user.locale, request.user.theme)
    registry = DelegateRegistry(
        [
            DelegateBinding(definition, _Stub(request.delegate_results.get(definition.id)))
            for definition in definitions.definitions()
        ]
    )
    interpreter = FlowInterpreter(registry)
    state = DialogState(uuid4(), user.id, user.chat_id, document.id, 1, node_id, "running", 0, data)
    capabilities = {**policy.capabilities, "eders_enabled": request.eders_enabled}
    try:
        state = await interpreter.settle(document, state, user, capabilities, "preview")
        node_id = state.node_id
        if request.event is not None:
            if request.event.user_id != user.id or request.event.chat_id != user.chat_id:
                raise InvalidEventError("Preview event identity does not match the context")
            state = replace(state, revision=request.event.expected_revision)
            result = await interpreter.advance(document, state, request.event, user, capabilities)
        else:
            result = ExecutionResult(state, nodes[state.node_id], "resumed")
        node_id, data = result.state.node_id, result.state.data
        rendered = FlowRenderer().render(document, result, user, capabilities)
    except (FlowExecutionError, InvalidEventError):
        return failed(
            [
                ContractIssue(
                    code="preview_execution",
                    path="/delegate_results",
                    message="Check delegate stubs, context and supported screen settings",
                )
            ]
        )
    return PreviewResult(
        node_id=node_id,
        data=data,
        issues=[],
        screen=PreviewScreen(
            text=rendered.text,
            keyboard=rendered.keyboard,
            feature=rendered.feature,
            return_flow=rendered.return_flow,
            buttons=[
                [PreviewButton(id=button.id, label=button.label, url=button.url) for button in row]
                for row in rendered.buttons
            ],
        ),
    )
