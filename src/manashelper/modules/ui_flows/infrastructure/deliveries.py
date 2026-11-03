from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import UiScreenDelivery
from ui_flows.domain.contracts import DeliveryStatus
from ui_flows.domain.delivery import Screen, ScreenDelivery


def _delivery(row: UiScreenDelivery) -> ScreenDelivery:
    return ScreenDelivery(
        row.token,
        row.session_id,
        row.revision,
        row.update_id,
        row.chat_id,
        Screen.model_validate(row.screen),
        cast(DeliveryStatus, row.status),
        row.message_id,
        row.operation_id,
        tuple(row.message_ids or []),
    )


class DeliveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def by_update(self, update_id: int) -> ScreenDelivery | None:
        row = await self._session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == update_id))
        return None if row is None else _delivery(row)

    async def by_operation(self, operation_id: UUID) -> ScreenDelivery | None:
        row = await self._session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.operation_id == operation_id))
        return None if row is None else _delivery(row)

    async def get(self, token: str, *, lock: bool = False) -> ScreenDelivery | None:
        statement = (
            select(UiScreenDelivery).where(UiScreenDelivery.token == token).execution_options(populate_existing=True)
        )
        row = await self._session.scalar(statement.with_for_update() if lock else statement)
        return None if row is None else _delivery(row)

    async def latest(self, session_id: UUID, revision: int) -> ScreenDelivery | None:
        row = await self._session.scalar(
            select(UiScreenDelivery)
            .where(
                UiScreenDelivery.session_id == session_id,
                UiScreenDelivery.revision == revision,
                UiScreenDelivery.status.in_(("sent", "unknown")),
            )
            .order_by(UiScreenDelivery.created_at.desc(), UiScreenDelivery.update_id.desc())
            .limit(1)
        )
        return None if row is None else _delivery(row)

    async def create(self, delivery: ScreenDelivery) -> None:
        self._session.add(
            UiScreenDelivery(
                token=delivery.token,
                session_id=delivery.session_id,
                update_id=delivery.update_id,
                operation_id=delivery.operation_id,
                revision=delivery.revision,
                chat_id=delivery.chat_id,
                screen=delivery.screen.model_dump(mode="json"),
                status=delivery.status,
                message_id=delivery.message_id,
                message_ids=list(delivery.message_ids),
            )
        )
        await self._session.flush()

    async def set_status(
        self,
        token: str,
        status: DeliveryStatus,
        message_id: int | None = None,
        *,
        message_ids: tuple[int, ...] | None = None,
    ) -> None:
        values: dict[str, Any] = dict(status=status, message_id=message_id)
        if message_ids is not None:
            values["message_ids"] = list(message_ids)
        await self._session.execute(update(UiScreenDelivery).where(UiScreenDelivery.token == token).values(**values))
