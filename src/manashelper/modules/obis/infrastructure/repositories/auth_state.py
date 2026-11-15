from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.obis.application.models import StoredObisAuthState
from manashelper.modules.obis.infrastructure.models.auth_state import ObisAuthState


class ObisAuthStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> StoredObisAuthState | None:
        row = await self._session.get(ObisAuthState, user_id, populate_existing=True)
        if row is None:
            return None
        return StoredObisAuthState(row.manual_required, row.reason, row.failures, row.retry_at, row.notified)

    async def save(self, user_id: int, state: StoredObisAuthState) -> None:
        await self._session.merge(
            ObisAuthState(
                user_id=user_id,
                manual_required=state.manual_required,
                reason=state.reason,
                failures=state.failures,
                retry_at=state.retry_at,
                notified=state.notified,
            )
        )

    async def delete(self, user_id: int) -> None:
        await self._session.execute(delete(ObisAuthState).where(ObisAuthState.user_id == user_id))
