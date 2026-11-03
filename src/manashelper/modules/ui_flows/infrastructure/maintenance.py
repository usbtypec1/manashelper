from datetime import datetime

from sqlalchemy import case, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery
from ui_flows.domain.state import ACTIVE_STATUSES


class FlowMaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def purge_closed(self, before: datetime) -> tuple[int, int]:
        closed = select(UiDialogSession.id).where(
            UiDialogSession.status.not_in(ACTIVE_STATUSES), UiDialogSession.updated_at < before
        )
        await self._session.execute(delete(UiInputSecret).where(UiInputSecret.session_id.in_(closed)))
        await self._session.execute(
            update(UiExternalOperation)
            .where(UiExternalOperation.session_id.in_(closed))
            .values(
                arguments={},
                result=None,
                status=case(
                    (UiExternalOperation.status == "succeeded", "applied"),
                    (UiExternalOperation.status == "pending", "failed"),
                    else_=UiExternalOperation.status,
                ),
                error_code=case(
                    (UiExternalOperation.status == "pending", "cancelled"), else_=UiExternalOperation.error_code
                ),
            )
        )
        deliveries = await self._session.scalars(
            delete(UiScreenDelivery)
            .where(UiScreenDelivery.session_id.in_(closed), UiScreenDelivery.created_at < before)
            .returning(UiScreenDelivery.token)
        )
        cleared = await self._session.scalars(
            update(UiDialogSession)
            .where(
                UiDialogSession.id.in_(closed),
                or_(UiDialogSession.data != {}, UiDialogSession.frames.is_not(None) & (UiDialogSession.frames != [])),
            )
            .values(data={}, frames=[], updated_at=UiDialogSession.updated_at)
            .returning(UiDialogSession.id)
        )
        # Retain session/event identities and metadata, so pruning never re-enables a business write.
        return len(cleared.all()), len(deliveries.all())
