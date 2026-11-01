from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.locations import LocationRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent
from ui_flows.domain.contracts import SessionStatus
from ui_flows.domain.state import ACTIVE_STATUSES, DialogState
from ui_flows.errors import DialogNotFoundError


def _state(row: UiDialogSession) -> DialogState:
    return DialogState(
        row.id,
        row.user_id,
        row.chat_id,
        row.flow_id,
        row.flow_version,
        row.node_id,
        cast(SessionStatus, row.status),
        row.revision,
        dict(row.data),
    )


class DialogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def atomic(self) -> AsyncIterator[None]:
        async with self._session.begin_nested():
            yield

    async def lock_chat(self, chat_id: int) -> None:
        # A transaction-scoped lock also serializes the first insert, when no session row exists.
        await self._session.execute(select(func.pg_advisory_xact_lock(chat_id)))

    async def active(self, chat_id: int) -> DialogState | None:
        row = await self._session.scalar(
            select(UiDialogSession)
            .where(
                UiDialogSession.chat_id == chat_id,
                UiDialogSession.status.in_(ACTIVE_STATUSES),
            )
            .execution_options(populate_existing=True)
        )
        return None if row is None else _state(row)

    async def get(self, session_id: UUID, *, lock: bool = False) -> DialogState:
        statement = (
            select(UiDialogSession).where(UiDialogSession.id == session_id).execution_options(populate_existing=True)
        )
        row = await self._session.scalar(statement.with_for_update() if lock else statement)
        if row is None:
            raise DialogNotFoundError("Dialog does not exist")
        return _state(row)

    async def processed_by(self, update_id: int) -> UUID | None:
        result: UUID | None = await self._session.scalar(
            select(UiFlowEvent.session_id).where(UiFlowEvent.update_id == update_id)
        )
        return result

    async def processed_result(self, update_id: int) -> DialogState:
        session_id = await self._session.scalar(
            select(func.coalesce(UiFlowEvent.result_session_id, UiFlowEvent.session_id)).where(
                UiFlowEvent.update_id == update_id
            )
        )
        if session_id is None:
            raise DialogNotFoundError("Processed event does not exist")
        return await self.get(session_id)

    async def create(self, state: DialogState) -> None:
        self._session.add(
            UiDialogSession(
                id=state.id,
                user_id=state.user_id,
                chat_id=state.chat_id,
                flow_id=state.flow_id,
                flow_version=state.flow_version,
                node_id=state.node_id,
                status=state.status,
                revision=state.revision,
                data=dict(state.data),
            )
        )
        await self._session.flush()

    async def save(self, state: DialogState) -> None:
        await self._session.execute(
            update(UiDialogSession)
            .where(UiDialogSession.id == state.id)
            .values(
                node_id=state.node_id,
                status=state.status,
                revision=state.revision,
                data=dict(state.data),
                updated_at=func.now(),
            )
        )

    async def record(
        self,
        state: DialogState,
        update_id: int,
        kind: str,
        from_step: str | None,
        outcome: str,
        *,
        result_state: DialogState | None = None,
    ) -> None:
        self._session.add(
            UiFlowEvent(
                update_id=update_id,
                session_id=state.id,
                result_session_id=result_state.id if result_state is not None else None,
                revision=state.revision,
                kind=kind,
                from_step=from_step,
                to_step=state.node_id,
                outcome=outcome,
            )
        )
        await self._session.flush()
        await LocationRepository(self._session).runtime(result_state or state, update_id, from_step, outcome)
