from dataclasses import replace
from typing import Literal
from uuid import UUID, uuid4

from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import FlowEvent, NavigationEvent
from ui_flows.domain.schema import EndNode
from ui_flows.domain.state import DialogState, ExecutionResult, RuntimeUser
from ui_flows.errors import (
    ActiveDialogError,
    DialogNotFoundError,
    FlowExecutionError,
    InvalidEventError,
    StaleEventError,
)
from ui_flows.ports.repositories import DialogStore, FlowStore


class DialogService:
    def __init__(
        self, dialogs: DialogStore, flows: FlowStore, interpreter: FlowInterpreter, policy: FlowPolicy
    ) -> None:
        self._dialogs = dialogs
        self._flows = flows
        self._interpreter = interpreter
        self._policy = policy

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

    async def start(
        self,
        flow_id: str,
        user: RuntimeUser,
        update_id: int,
        *,
        replace_active: bool = False,
        navigation: Literal["study"] | None = None,
        follow_returns: bool = False,
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
                if state.flow_id != flow_id:
                    raise InvalidEventError("The update already belongs to another scenario")
                return await self._duplicate(await self._dialogs.processed_result(update_id))
            active = await self._dialogs.active(user.chat_id)
            if active is not None:
                if not replace_active:
                    raise ActiveDialogError("The chat already has an active dialog")
                await self._dialogs.save(replace(active, status="cancelled", revision=active.revision + 1))
            version = await self._flows.published(flow_id)
            entry = (
                version.document.navigation_entries.get(navigation, version.document.entry)
                if navigation
                else version.document.entry
            )
            state = DialogState(
                uuid4(),
                user.id,
                user.chat_id,
                flow_id,
                version.version,
                entry,
                "running",
                0,
                dict(version.document.initial_data),
            )
            await self._dialogs.create(state)
            settled = await self._interpreter.settle(
                version.document, state, user, self._policy.capabilities, str(update_id)
            )
            await self._dialogs.save(settled)
            returned_from = None
            if follow_returns:
                settled, returned_from = await self._return(settled, user, update_id)
            await self._dialogs.record(
                returned_from or settled,
                update_id,
                "start",
                active.node_id if active else None,
                "started",
                result_state=settled if returned_from is not None else None,
            )
            current = await self._flows.version(settled.flow_id, settled.flow_version)
            node = next(node for node in current.document.nodes if node.id == settled.node_id)
            return ExecutionResult(settled, node, "started", returned_from)

    async def _return(
        self, state: DialogState, user: RuntimeUser, update_id: int
    ) -> tuple[DialogState, DialogState | None]:
        version = await self._flows.version(state.flow_id, state.flow_version)
        node = next(node for node in version.document.nodes if node.id == state.node_id)
        if not isinstance(node, EndNode) or node.return_flow is None:
            return state, None
        target = await self._flows.published(node.return_flow)
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
        )
        await self._dialogs.create(following)
        following = await self._interpreter.settle(
            target.document, following, user, self._policy.capabilities, str(update_id)
        )
        await self._dialogs.save(following)
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
            result = await self._interpreter.advance(version.document, state, event, user, self._policy.capabilities)
            await self._dialogs.save(result.state)
            if follow_returns:
                following, previous = await self._return(result.state, user, event.update_id)
                if previous is not None:
                    target = await self._flows.version(following.flow_id, following.flow_version)
                    node = next(node for node in target.document.nodes if node.id == following.node_id)
                    result = ExecutionResult(following, node, result.outcome, previous)
            await self._dialogs.record(
                result.returned_from or result.state,
                event.update_id,
                event.kind,
                state.node_id,
                result.outcome,
                result_state=result.state if result.returned_from is not None else None,
            )
            return result
