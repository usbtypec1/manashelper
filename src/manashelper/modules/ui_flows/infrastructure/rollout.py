from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowRollout
from ui_flows.domain.rollout import RolloutMode, RolloutState
from ui_flows.domain.state import ACTIVE_STATUSES
from ui_flows.errors import FlowConflictError


class RolloutRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure(self) -> None:
        await self._session.execute(
            insert(UiFlowRollout).values(id=1, mode="admin", revision=0).on_conflict_do_nothing()
        )

    async def get(self, *, lock: bool = False) -> RolloutState:
        if lock:
            await self.ensure()
        statement = select(UiFlowRollout).where(UiFlowRollout.id == 1).execution_options(populate_existing=True)
        row = await self._session.scalar(statement.with_for_update(read=True) if lock else statement)
        return (
            RolloutState()
            if row is None
            else RolloutState(cast(RolloutMode, row.mode), row.revision, row.updated_at, row.updated_by)
        )

    async def set(self, mode: RolloutMode, expected_revision: int, author_id: int) -> RolloutState:
        async with self._session.begin_nested():
            await self.ensure()
            result = await self._session.scalar(
                update(UiFlowRollout)
                .where(UiFlowRollout.id == 1, UiFlowRollout.revision == expected_revision)
                .values(mode=mode, revision=expected_revision + 1, updated_at=func.now(), updated_by=author_id)
                .returning(UiFlowRollout.id)
            )
            if result is None:
                raise FlowConflictError("The rollout revision has changed")
            return await self.get()

    async def active_count(self) -> int:
        return int(
            await self._session.scalar(
                select(func.count()).select_from(UiDialogSession).where(UiDialogSession.status.in_(ACTIVE_STATUSES))
            )
            or 0
        )
