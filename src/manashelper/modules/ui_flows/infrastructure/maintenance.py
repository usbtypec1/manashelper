from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery
from ui_flows.domain.state import ACTIVE_STATUSES


class FlowMaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def purge_closed(self, before: datetime) -> tuple[int, int]:
        closed = select(UiDialogSession.id).where(
            UiDialogSession.status.not_in(ACTIVE_STATUSES), UiDialogSession.updated_at < before
        )
        deliveries = await self._session.scalars(
            delete(UiScreenDelivery)
            .where(UiScreenDelivery.session_id.in_(closed), UiScreenDelivery.created_at < before)
            .returning(UiScreenDelivery.token)
        )
        cleared = await self._session.scalars(
            update(UiDialogSession)
            .where(UiDialogSession.id.in_(closed), UiDialogSession.data != {})
            .values(data={}, updated_at=UiDialogSession.updated_at)
            .returning(UiDialogSession.id)
        )
        # Retain session/event identities and metadata, so pruning never re-enables a business write.
        return len(cleared.all()), len(deliveries.all())
