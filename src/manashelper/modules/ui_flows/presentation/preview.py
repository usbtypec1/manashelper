from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from manashelper.modules.ui_flows.presentation.admin_contracts import (
    PreviewButton,
    PreviewDelegateResult,
    PreviewFrame,
    PreviewPosition,
    PreviewRequest,
    PreviewResult,
    PreviewScreen,
)
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.service import TextCatalogService
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.application.execution import ScenarioExecutor
from ui_flows.application.flows import FlowService
from ui_flows.application.interpreter import FlowInterpreter, StepBudget
from ui_flows.application.policy import FlowPolicy
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import ButtonEvent, ContractIssue, DelegateContext, DelegateResult
from ui_flows.domain.schema import CallNode, DataValue, InputNode
from ui_flows.domain.state import CallFrame, DialogState, ExecutionResult, PublishedFlow, RuntimeUser
from ui_flows.errors import FlowExecutionError, FlowNotFoundError, InvalidEventError, InvalidFlowError


class _Stub:
    def __init__(self, result: PreviewDelegateResult | None) -> None:
        self._result = result

    async def __call__(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        if self._result is None:
            raise FlowExecutionError("A preview delegate result is required")
        return DelegateResult(self._result.outcome, self._result.values)


class _PreviewVersions:
    def __init__(self, versions: dict[tuple[str, int], PublishedFlow]) -> None:
        self.versions = versions

    async def version(self, flow_id: str, version: int) -> PublishedFlow:
        try:
            return self.versions[flow_id, version]
        except KeyError:
            raise FlowExecutionError("Preview position is outside the dependency manifest") from None


async def preview(
    request: PreviewRequest,
    definitions: DelegateRegistry,
    policy: FlowPolicy,
    *,
    flows: FlowService | None = None,
    texts: TextCatalogService | None = None,
) -> PreviewResult:
    document = request.document
    node_id = request.node_id or document.entry
    data = {**document.initial_data, **request.data}

    def failed(issues: list[ContractIssue]) -> PreviewResult:
        return PreviewResult(node_id=node_id, data=data, screen=None, issues=issues)

    try:
        policy.validate(document, definitions)
        pins = (
            request.position.dependencies
            if request.position is not None
            else (await flows.pin_dependencies(document) if flows else {})
        )
        if flows:
            await flows.validate_dependencies(document, dependencies=pins)
    except InvalidFlowError as error:
        return failed(error.issues)
    versions = _PreviewVersions(
        {(document.id, 0): PublishedFlow(document, 0, 0, 0, datetime.now(UTC), i18n.current_catalog.release_id, pins)}
    )
    if request.position is None and not any(node.id == node_id for node in document.nodes):
        return failed([ContractIssue(code="unknown_node", path="/node_id", message="Node does not exist")])
    if (
        request.user.id <= 0
        or request.user.chat_id != request.user.id
        or (
            request.position is None
            and any(
                name not in document.fields or not accepts_scalar(document.fields[name], value)
                for name, value in data.items()
            )
        )
    ):
        return failed([ContractIssue(code="invalid_context", path="/data", message="Preview context is invalid")])
    user = RuntimeUser(request.user.id, request.user.chat_id, request.user.locale, request.user.theme)
    registry = DelegateRegistry(
        [
            DelegateBinding(
                definition.model_copy(update={"effect": "read"}) if definition.effect == "external" else definition,
                _Stub(request.delegate_results.get(definition.id)),
            )
            for definition in definitions.definitions()
        ]
    )
    interpreter = FlowInterpreter(registry)
    position = request.position
    state = DialogState(
        uuid4(),
        user.id,
        user.chat_id,
        position.flow_id if position else document.id,
        position.flow_version if position else 0,
        position.node_id if position else node_id,
        "running",
        0,
        position.data if position else data,
        frames=tuple(
            CallFrame(frame.flow_id, frame.flow_version, frame.node_id, frame.data) for frame in position.frames
        )
        if position
        else (),
    )
    capabilities = {**policy.capabilities, "eders_enabled": request.eders_enabled}
    try:
        pending = list(pins.items())
        while pending:
            flow_id, version_id = pending.pop()
            if (flow_id, version_id) in versions.versions:
                continue
            if flows is None or len(versions.versions) >= 256:
                raise FlowExecutionError("Preview dependencies are unavailable")
            published = await flows.version(flow_id, version_id)
            versions.versions[flow_id, version_id] = published
            pending.extend(published.dependencies.items())
        current = await versions.version(state.flow_id, state.flow_version)
        for index, frame in enumerate(state.frames):
            if position is not None and position.frames[index].resume_status is not None:
                raise FlowExecutionError("Global interrupts are not authored preview continuations")
            parent = await versions.version(frame.flow_id, frame.flow_version)
            call = next((item for item in parent.document.nodes if item.id == frame.node_id), None)
            following = state.frames[index + 1] if index + 1 < len(state.frames) else state
            if (
                not isinstance(call, CallNode)
                or call.flow != following.flow_id
                or parent.dependencies.get(call.flow) != following.flow_version
                or any(
                    name not in parent.document.fields or not accepts_scalar(parent.document.fields[name], value)
                    for name, value in frame.data.items()
                )
            ):
                raise FlowExecutionError("Preview caller frame is invalid")
        if not any(item.id == state.node_id for item in current.document.nodes) or any(
            name not in current.document.fields or not accepts_scalar(current.document.fields[name], value)
            for name, value in state.data.items()
        ):
            raise FlowExecutionError("Preview position is invalid")
        executor = ScenarioExecutor(interpreter, versions, capabilities)
        budget = StepBudget()
        state = (await executor.settle(state, user, "preview", budget)).state
        node_id = state.node_id
        current = await versions.version(state.flow_id, state.flow_version)
        nodes = {node.id: node for node in current.document.nodes}
        if request.event is not None:
            if request.event.user_id != user.id or request.event.chat_id != user.chat_id:
                raise InvalidEventError("Preview event identity does not match the context")
            state = replace(state, revision=request.event.expected_revision)
            preview_event = request.event
            if isinstance(preview_event, ButtonEvent) and preview_event.snapshot is not None:
                # Preview requests are editable client data; choose the action from a fresh safe render.
                snapshot = await texts.version(current.text_catalog_release or 1) if texts else i18n.current_catalog
                displayed = FlowRenderer().render(
                    current.document,
                    ExecutionResult(state, nodes[state.node_id], "resumed"),
                    user,
                    capabilities,
                    snapshot,
                )
                action = next(
                    (button for row in displayed.buttons for button in row if button.id == preview_event.button_id),
                    None,
                )
                if action is None:
                    raise InvalidEventError("Preview action is unavailable")
                preview_event = preview_event.model_copy(update={"snapshot": action.snapshot})
            result = await interpreter.advance(current.document, state, preview_event, user, capabilities, budget)
            if result.outcome == "advanced":
                state = (await executor.settle(result.state, user, "preview", budget)).state
                current = await versions.version(state.flow_id, state.flow_version)
                result = ExecutionResult(
                    state, next(item for item in current.document.nodes if item.id == state.node_id), result.outcome
                )
        else:
            result = ExecutionResult(state, nodes[state.node_id], "resumed")
        node_id, data = result.state.node_id, result.state.data
        snapshot = await texts.version(current.text_catalog_release or 1) if texts else i18n.current_catalog
        rendered = FlowRenderer().render(current.document, result, user, capabilities, snapshot)
    except (FlowExecutionError, FlowNotFoundError, InvalidEventError):
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
        position=PreviewPosition(
            flow_id=result.state.flow_id,
            flow_version=result.state.flow_version,
            node_id=result.state.node_id,
            data=result.state.data,
            frames=[PreviewFrame(**asdict(frame)) for frame in result.state.frames],
            dependencies=pins,
        ),
        node_kind=result.node.kind if result.node.kind in {"menu", "input", "end", "return"} else None,
        screen=PreviewScreen(
            text=rendered.text,
            messages=rendered.messages,
            media=rendered.media,
            contact_request=rendered.contact_request,
            input_type=result.node.input_type if isinstance(result.node, InputNode) else None,
            keyboard=rendered.keyboard,
            feature=rendered.feature,
            return_flow=rendered.return_flow,
            buttons=[
                [
                    PreviewButton(id=button.id, label=button.label, url=button.url, snapshot=button.snapshot)
                    for button in row
                ]
                for row in rendered.buttons
            ],
        ),
    )
