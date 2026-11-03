"""Drive automatic steps and typed scenario frames under the caller's transaction."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol
from uuid import uuid4

from ui_flows.application.composition import MAX_CALL_DEPTH
from ui_flows.application.interpreter import EvaluationContext, FlowInterpreter, StepBudget
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.schema import CallNode, EndNode, ReplaceNode, ReturnNode, Scalar
from ui_flows.domain.state import CallFrame, DialogState, PublishedFlow, RuntimeUser
from ui_flows.errors import FlowExecutionError


class VersionReader(Protocol):
    async def version(self, flow_id: str, version: int) -> PublishedFlow: ...


@dataclass(frozen=True, slots=True)
class Settlement:
    state: DialogState
    closed: tuple[DialogState, ...] = ()
    notices: tuple[DialogState, ...] = ()


class ScenarioExecutor:
    def __init__(
        self, interpreter: FlowInterpreter, versions: VersionReader, capabilities: Mapping[str, Scalar]
    ) -> None:
        self._interpreter = interpreter
        self._versions = versions
        self._capabilities = capabilities

    async def settle(
        self, state: DialogState, user: RuntimeUser, event_id: str, budget: StepBudget | None = None
    ) -> Settlement:
        budget = budget or StepBudget()
        closed = []
        notices: list[DialogState] = []
        while True:
            version = await self._versions.version(state.flow_id, state.flow_version)
            document = version.document
            state = await self._interpreter.settle(document, state, user, self._capabilities, event_id, budget)
            node = next(item for item in document.nodes if item.id == state.node_id)
            context = EvaluationContext(document, dict(state.data), user, self._capabilities)
            if isinstance(node, (CallNode, ReplaceNode)):
                budget.consume()
                if node.flow not in version.dependencies:
                    raise FlowExecutionError("A published scenario dependency is missing")
                target = await self._versions.version(node.flow, version.dependencies[node.flow])
                values = {name: context.resolve(value) for name, value in node.arguments.items()}
                if values.keys() != target.document.inputs.keys() or any(
                    not accepts_scalar(target.document.inputs[name], value) for name, value in values.items()
                ):
                    raise FlowExecutionError("Scenario input contract does not match")
                frames: tuple[CallFrame, ...] = ()
                if isinstance(node, CallNode):
                    if len(state.frames) + 1 >= MAX_CALL_DEPTH:
                        raise FlowExecutionError("Maximum scenario depth exceeded")
                    frames = (*state.frames, CallFrame(state.flow_id, state.flow_version, node.id, dict(state.data)))
                else:
                    closed.append(replace(state, status="cancelled"))
                state = replace(
                    state,
                    id=state.id if isinstance(node, CallNode) else uuid4(),
                    revision=state.revision if isinstance(node, CallNode) else 0,
                    flow_id=target.document.id,
                    flow_version=target.version,
                    node_id=target.document.entry,
                    data={**target.document.initial_data, **values},
                    frames=frames,
                    status="running",
                    effect_revision=None,
                )
                continue
            if isinstance(node, ReturnNode) or (
                isinstance(node, EndNode) and state.frames and node.status != "handed_off"
            ):
                budget.consume()
                outcome = node.outcome if isinstance(node, ReturnNode) else node.status
                values = (
                    {name: context.resolve(value) for name, value in node.values.items()}
                    if isinstance(node, ReturnNode)
                    else {}
                )
                if (
                    outcome not in document.outcomes
                    or values.keys() != document.outputs.keys()
                    or any(not accepts_scalar(document.outputs[name], value) for name, value in values.items())
                ):
                    raise FlowExecutionError("Scenario output contract does not match")
                if not state.frames:
                    return Settlement(replace(state, status="completed"), tuple(closed), tuple(notices))
                frame = state.frames[-1]
                parent = await self._versions.version(frame.flow_id, frame.flow_version)
                if node.text:
                    notices.append(state)
                if frame.resume_status is not None:
                    if document.outputs or not any(item.id == frame.node_id for item in parent.document.nodes):
                        raise FlowExecutionError("The interrupted continuation is unavailable")
                    state = replace(
                        state,
                        flow_id=frame.flow_id,
                        flow_version=frame.flow_version,
                        node_id=frame.node_id,
                        data=dict(frame.data),
                        frames=state.frames[:-1],
                        status=frame.resume_status,
                        trigger_release=frame.trigger_release,
                        effect_revision=frame.effect_revision
                        if frame.effect_revision is not None
                        else (frame.revision if frame.resume_status == "waiting_effect" else None),
                    )
                    # The parent is already at a wait: never repeat its entry action or external work.
                    return Settlement(state, tuple(closed), tuple(notices))
                call = next((item for item in parent.document.nodes if item.id == frame.node_id), None)
                if not isinstance(call, CallNode) or call.flow != state.flow_id or outcome not in call.outcomes:
                    raise FlowExecutionError("The parent continuation is unavailable")
                restored = dict(frame.data)
                for output, destination in call.results.items():
                    if (
                        output not in values
                        or destination not in parent.document.fields
                        or not accepts_scalar(parent.document.fields[destination], values[output])
                    ):
                        raise FlowExecutionError("Scenario output destination does not match")
                    restored[destination] = values[output]
                state = replace(
                    state,
                    flow_id=frame.flow_id,
                    flow_version=frame.flow_version,
                    node_id=call.outcomes[outcome],
                    data=restored,
                    frames=state.frames[:-1],
                    status="running",
                )
                continue
            return Settlement(state, tuple(closed), tuple(notices))
