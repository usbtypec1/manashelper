from collections.abc import Mapping
from dataclasses import replace
from typing import Literal
from uuid import UUID, uuid4

from ui_flows.application.composition import MAX_CALL_DEPTH
from ui_flows.application.execution import ScenarioExecutor, Settlement
from ui_flows.application.ingress import idle_menu
from ui_flows.application.interpreter import EvaluationContext, FlowInterpreter, StepBudget
from ui_flows.application.policy import FlowPolicy
from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import FlowEvent, NavigationEvent
from ui_flows.domain.effects import ExternalOperation
from ui_flows.domain.ingress import ExpectedPosition
from ui_flows.domain.schema import ActionNode, DataValue, EndNode
from ui_flows.domain.state import CallFrame, DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import (
    ActiveDialogError,
    DialogNotFoundError,
    FlowExecutionError,
    InvalidEventError,
    StaleEventError,
)
from ui_flows.ports.effects import EffectStore
from ui_flows.ports.repositories import DialogStore, FlowStore


class DialogService:
    def __init__(
        self,
        dialogs: DialogStore,
        flows: FlowStore,
        interpreter: FlowInterpreter,
        policy: FlowPolicy,
        effects: EffectStore | None = None,
    ) -> None:
        self._dialogs = dialogs
        self._flows = flows
        self._interpreter = interpreter
        self._policy = policy
        self._executor = ScenarioExecutor(interpreter, flows, policy.capabilities)
        self._effects = effects

    @staticmethod
    def _check_user(user: RuntimeUser) -> None:
        if user.id <= 0 or user.chat_id != user.id:
            raise InvalidEventError("Runtime dialogs require a private user chat")

    @staticmethod
    def _check_owner(state: DialogState, user: RuntimeUser) -> None:
        if (state.user_id, state.chat_id) != (user.id, user.chat_id):
            raise DialogNotFoundError("Dialog does not exist")

    async def _duplicate(self, state: DialogState) -> ExecutionResult:
        version = await self._flows.version(state.flow_id, state.flow_version)
        node = next(node for node in version.document.nodes if node.id == state.node_id)
        return ExecutionResult(state, node, "duplicate")

    async def get(self, session_id: UUID, user: RuntimeUser) -> DialogState:
        self._check_user(user)
        state = await self._dialogs.get(session_id)
        self._check_owner(state, user)
        return state

    async def active(self, user: RuntimeUser) -> DialogState | None:
        self._check_user(user)
        state = await self._dialogs.active(user.chat_id)
        if state is not None:
            self._check_owner(state, user)
        return state

    async def cancel_active(self, user: RuntimeUser, update_id: int) -> None:
        self._check_user(user)
        async with self._dialogs.atomic():
            await self._dialogs.lock_chat(user.chat_id)
            state = await self.active(user)
            if state is not None:
                await self.handle(
                    NavigationEvent(
                        kind="navigation",
                        action="cancel",
                        update_id=update_id,
                        user_id=user.id,
                        chat_id=user.chat_id,
                        session_id=str(state.id),
                        expected_revision=state.revision,
                    ),
                    user,
                )

    async def _save_settlement(self, settled: Settlement, user: RuntimeUser) -> None:
        for index, closed in enumerate(settled.closed):
            if index == 0:
                await self._dialogs.save(closed)
            else:
                await self._dialogs.create(closed)
        if settled.closed:
            await self._dialogs.create(settled.state)
        else:
            await self._dialogs.save(settled.state)
        if settled.state.status == "waiting_effect" and settled.state.effect_revision is None:
            if self._effects is None:
                raise FlowExecutionError("External operations are unavailable")
            state = settled.state
            version = await self._flows.version(state.flow_id, state.flow_version)
            node = next(item for item in version.document.nodes if item.id == state.node_id)
            if not isinstance(node, ActionNode):
                raise FlowExecutionError("Only an external action can wait for an operation")
            context = EvaluationContext(version.document, dict(state.data), user, self._policy.capabilities)
            arguments = {name: context.resolve(value) for name, value in node.arguments.items()}
            self._interpreter.validate_arguments(node.delegate, node.contract_version, arguments)
            await self._effects.prepare(
                ExternalOperation(
                    uuid4(),
                    state.id,
                    state.user_id,
                    state.chat_id,
                    state.revision,
                    state.flow_id,
                    state.flow_version,
                    node.id,
                    node.delegate,
                    node.contract_version,
                    arguments,
                )
            )

    async def interrupt(
        self,
        flow_id: str,
        user: RuntimeUser,
        update_id: int,
        *,
        trigger_release: int | None = None,
        arguments: Mapping[str, DataValue] | None = None,
        position: ExpectedPosition | None = None,
    ) -> ExecutionResult:
        """Call a pinned preference dialog and resume the exact suspended wait on Return."""
        self._check_user(user)
        if type(update_id) is not int or update_id < 0:
            raise InvalidEventError("Invalid update identity")
        async with self._dialogs.atomic():
            await self._dialogs.lock_chat(user.chat_id)
            processed = await self._dialogs.processed_by(update_id)
            if processed is not None:
                prior = await self._dialogs.get(processed)
                self._check_owner(prior, user)
                return await self._duplicate(await self._dialogs.processed_result(update_id))
            active = await self.active(user)
            if position is not None and not position.matches(active):
                raise StaleEventError("The admitted chat position has changed")
            if active is None:
                return await self.start(flow_id, user, update_id, trigger_release=trigger_release, arguments=arguments)
            if active.status not in {"waiting_button", "waiting_input", "waiting_effect"}:
                raise ActiveDialogError("The active scenario cannot be interrupted here")
            if len(active.frames) + 1 >= MAX_CALL_DEPTH:
                raise FlowExecutionError("Maximum scenario depth exceeded")
            version = (
                await self._flows.from_release(flow_id, trigger_release)
                if trigger_release is not None
                else await self._flows.published(flow_id)
            )
            if version.document.outputs:
                raise FlowExecutionError("An interrupt must not export parent data")
            values = {**version.document.initial_data, **dict(arguments or {})}
            if not version.document.inputs.keys() <= values.keys() or any(
                name not in version.document.fields or not accepts_scalar(version.document.fields[name], value)
                for name, value in values.items()
            ):
                raise InvalidEventError("Interrupt arguments do not match the declared scenario fields")
            frame = CallFrame(
                active.flow_id,
                active.flow_version,
                active.node_id,
                dict(active.data),
                resume_status=active.status,
                revision=active.revision,
                trigger_release=active.trigger_release,
                effect_revision=active.effect_revision,
            )
            following = replace(
                active,
                flow_id=flow_id,
                flow_version=version.version,
                node_id=version.document.entry,
                status="running",
                revision=active.revision + 1,
                data=values,
                frames=(*active.frames, frame),
                trigger_release=trigger_release,
                effect_revision=None,
            )
            settled = await self._executor.settle(following, user, str(update_id))
            await self._save_settlement(settled, user)
            await self._dialogs.record(settled.state, update_id, "interrupt", active.node_id, "started")
            current = await self._flows.version(settled.state.flow_id, settled.state.flow_version)
            node = next(item for item in current.document.nodes if item.id == settled.state.node_id)
            return ExecutionResult(settled.state, node, "started", notices=settled.notices)

    async def start(
        self,
        flow_id: str,
        user: RuntimeUser,
        update_id: int,
        *,
        replace_active: bool = False,
        navigation: Literal["study"] | None = None,
        follow_returns: bool = False,
        trigger_release: int | None = None,
        entry: str | None = None,
        arguments: Mapping[str, DataValue] | None = None,
        replace_idle_menu: str | None = None,
        position: ExpectedPosition | None = None,
    ) -> ExecutionResult:
        self._check_user(user)
        if type(update_id) is not int or update_id < 0:
            raise InvalidEventError("Invalid update identity")
        async with self._dialogs.atomic():
            await self._dialogs.lock_chat(user.chat_id)
            processed = await self._dialogs.processed_by(update_id)
            if processed is not None:
                state = await self._dialogs.get(processed)
                self._check_owner(state, user)
                if state.root_flow_id != flow_id:
                    raise InvalidEventError("The update already belongs to another scenario")
                return await self._duplicate(await self._dialogs.processed_result(update_id))
            active = await self._dialogs.active(user.chat_id)
            if position is not None and not position.matches(active):
                raise StaleEventError("The admitted chat position has changed")
            if active is not None:
                if not replace_active and not (replace_idle_menu is not None and idle_menu(active, replace_idle_menu)):
                    raise ActiveDialogError("The chat already has an active dialog")
                await self._dialogs.save(replace(active, status="cancelled", revision=active.revision + 1))
            version = (
                (await self._flows.from_release(flow_id, trigger_release))
                if trigger_release is not None
                else await self._flows.published(flow_id)
            )
            selected_entry = entry or (
                version.document.navigation_entries.get(navigation, version.document.entry)
                if navigation
                else version.document.entry
            )
            if not any(node.id == selected_entry for node in version.document.nodes):
                raise FlowExecutionError("Entry is unavailable in this scenario version")
            values = dict(version.document.initial_data)
            for field, value in (arguments or {}).items():
                declaration = version.document.fields.get(field)
                if declaration is None or not accepts_scalar(declaration, value):
                    raise InvalidEventError("Launch arguments do not match the declared scenario fields")
                values[field] = value
            if not version.document.inputs.keys() <= values.keys():
                raise InvalidEventError("Required scenario inputs are missing")
            state = DialogState(
                uuid4(),
                user.id,
                user.chat_id,
                flow_id,
                version.version,
                selected_entry,
                "running",
                0,
                values,
                trigger_release,
            )
            await self._dialogs.create(state)
            settlement = await self._executor.settle(state, user, str(update_id))
            await self._save_settlement(settlement, user)
            settled = settlement.state
            replaced_from = settlement.closed[0] if settlement.closed else None
            returned_from = None
            if follow_returns:
                settled, returned_from = await self._return(settled, user, update_id)
            await self._dialogs.record(
                replaced_from or returned_from or settled,
                update_id,
                "start",
                active.node_id if active else None,
                "started",
                result_state=settled if returned_from is not None or replaced_from is not None else None,
            )
            current = await self._flows.version(settled.flow_id, settled.flow_version)
            node = next(node for node in current.document.nodes if node.id == settled.node_id)
            return ExecutionResult(settled, node, "started", returned_from, replaced_from, settlement.notices)

    async def _return(
        self, state: DialogState, user: RuntimeUser, update_id: int
    ) -> tuple[DialogState, DialogState | None]:
        version = await self._flows.version(state.flow_id, state.flow_version)
        node = next(node for node in version.document.nodes if node.id == state.node_id)
        if not isinstance(node, EndNode) or node.return_flow is None:
            return state, None
        target = (
            (await self._flows.from_release(node.return_flow, state.trigger_release))
            if state.trigger_release is not None
            else await self._flows.published(node.return_flow)
        )
        # A return opens a screen, not another automatic workflow. This also bounds cross-flow cycles.
        entry = next(node for node in target.document.nodes if node.id == target.document.entry)
        if entry.kind not in {"menu", "input"}:
            raise FlowExecutionError("A return scenario must start at an interactive screen")
        following = DialogState(
            uuid4(),
            user.id,
            user.chat_id,
            target.document.id,
            target.version,
            target.document.entry,
            "running",
            0,
            dict(target.document.initial_data),
            state.trigger_release,
        )
        await self._dialogs.create(following)
        settlement = await self._executor.settle(following, user, str(update_id))
        await self._save_settlement(settlement, user)
        following = settlement.state
        return following, state

    async def handle(self, event: FlowEvent, user: RuntimeUser, *, follow_returns: bool = False) -> ExecutionResult:
        self._check_user(user)
        if (event.user_id, event.chat_id) != (user.id, user.chat_id):
            raise InvalidEventError("Event identity does not match the authenticated user")
        try:
            session_id = UUID(event.session_id)
        except ValueError:
            raise DialogNotFoundError("Dialog does not exist") from None
        async with self._dialogs.atomic():
            await self._dialogs.lock_chat(user.chat_id)
            state = await self._dialogs.get(session_id, lock=True)
            self._check_owner(state, user)
            processed = await self._dialogs.processed_by(event.update_id)
            if processed is not None:
                if processed != state.id:
                    raise InvalidEventError("The update already belongs to another dialog")
                return await self._duplicate(await self._dialogs.processed_result(event.update_id))
            if state.revision != event.expected_revision:
                raise StaleEventError("The screen revision has changed")
            version = await self._flows.version(state.flow_id, state.flow_version)
            budget = StepBudget()
            result = await self._interpreter.advance(
                version.document, state, event, user, self._policy.capabilities, budget
            )
            if result.outcome == "advanced":
                settlement = await self._executor.settle(result.state, user, str(event.update_id), budget)
                await self._save_settlement(settlement, user)
                settled = settlement.state
                current = await self._flows.version(settled.flow_id, settled.flow_version)
                result = ExecutionResult(
                    settled,
                    next(node for node in current.document.nodes if node.id == settled.node_id),
                    result.outcome,
                    replaced_from=settlement.closed[0] if settlement.closed else None,
                    notices=settlement.notices,
                )
            await self._dialogs.save(result.state)
            if follow_returns:
                following, previous = await self._return(result.state, user, event.update_id)
                if previous is not None:
                    target = await self._flows.version(following.flow_id, following.flow_version)
                    node = next(node for node in target.document.nodes if node.id == following.node_id)
                    result = ExecutionResult(
                        following, node, result.outcome, previous, result.replaced_from, result.notices
                    )
            await self._dialogs.record(
                result.replaced_from or result.returned_from or result.state,
                event.update_id,
                event.kind,
                state.node_id,
                result.outcome,
                result_state=result.state
                if result.returned_from is not None or result.replaced_from is not None
                else None,
            )
            return result

    async def apply_effect(self, operation_id: UUID, user: RuntimeUser) -> ExecutionResult | None:
        self._check_user(user)
        if self._effects is None:
            raise FlowExecutionError("External operations are unavailable")
        async with self._dialogs.atomic():
            await self._dialogs.lock_chat(user.chat_id)
            operation = await self._effects.get(operation_id, lock=True)
            if operation is None or (operation.user_id, operation.chat_id) != (user.id, user.chat_id):
                raise InvalidEventError("External operation identity does not match")
            if operation.status != "succeeded" or operation.result is None:
                return None
            state = await self._dialogs.get(operation.session_id, lock=True)
            active = await self._dialogs.active(user.chat_id)
            if active is None or active.id != state.id or not operation.matches_position(state, suspended=True):
                await self._effects.mark_applied(operation_id)
                return None
            if not operation.matches_position(state):
                return None  # The owning wait is suspended; keep the saved result until its Return.
            version = await self._flows.version(state.flow_id, state.flow_version)
            node = next(item for item in version.document.nodes if item.id == state.node_id)
            if not isinstance(node, ActionNode) or (node.delegate, node.contract_version) != (
                operation.delegate_id,
                operation.contract_version,
            ):
                raise FlowExecutionError("External operation continuation does not match")
            result = self._interpreter.validate_result(node.delegate, node.contract_version, operation.result)
            values = dict(state.data)
            for name, destination in node.results.items():
                if name not in result.values or not accepts_scalar(
                    version.document.fields[destination], result.values[name]
                ):
                    raise FlowExecutionError("External result cannot be assigned")
                values[destination] = result.values[name]
            following = replace(
                state,
                node_id=node.outcomes[result.outcome],
                data=values,
                status="running",
                revision=state.revision + 1,
                effect_revision=None,
            )
            settled = await self._executor.settle(following, user, str(operation.id))
            await self._save_settlement(settled, user)
            await self._effects.mark_applied(operation_id)
            await self._dialogs.record_effect(settled.state, operation_id, node.id, result.outcome)
            current = await self._flows.version(settled.state.flow_id, settled.state.flow_version)
            return ExecutionResult(
                settled.state,
                next(item for item in current.document.nodes if item.id == settled.state.node_id),
                "advanced",
                notices=settled.notices,
            )
