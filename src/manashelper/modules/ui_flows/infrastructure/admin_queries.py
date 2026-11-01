from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.orm import (
    UiDialogSession,
    UiFlow,
    UiFlowVersion,
    UiScreenDelivery,
    UiUserLocation,
    UiUserTransition,
)
from ui_flows.domain.admin import FlowInfo, LocationInfo, TransitionInfo, VersionInfo
from ui_flows.domain.contracts import DeliveryStatus, SessionStatus


class AdminQueriesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def flows(self, after: str | None, limit: int) -> list[FlowInfo]:
        query = select(UiFlow.id, UiFlow.draft_revision, UiFlow.published_version).order_by(UiFlow.id).limit(limit)
        if after is not None:
            query = query.where(UiFlow.id > after)
        return [FlowInfo(*row) for row in (await self._session.execute(query)).all()]

    async def versions(self, flow_id: str, before: int | None, limit: int) -> list[VersionInfo]:
        query = select(
            UiFlowVersion.flow_id,
            UiFlowVersion.version,
            UiFlowVersion.draft_revision,
            UiFlowVersion.published_at,
            UiFlowVersion.author_id,
        ).where(UiFlowVersion.flow_id == flow_id)
        if before is not None:
            query = query.where(UiFlowVersion.version < before)
        rows = (await self._session.execute(query.order_by(UiFlowVersion.version.desc()).limit(limit))).all()
        return [VersionInfo(*row) for row in rows]

    async def locations(self, user_ids: list[int]) -> list[LocationInfo]:
        delivery = (
            select(UiScreenDelivery.status)
            .where(
                UiScreenDelivery.session_id == UiDialogSession.id,
                UiScreenDelivery.revision == UiDialogSession.revision,
            )
            .order_by(UiScreenDelivery.created_at.desc(), UiScreenDelivery.update_id.desc())
            .limit(1)
            .scalar_subquery()
        )
        # Project metadata explicitly: never SELECT session.data into monitoring results.
        query = (
            select(
                UiUserLocation.user_id,
                UiUserLocation.chat_id,
                UiUserLocation.owner,
                UiUserLocation.legacy_state,
                UiUserLocation.handler,
                UiUserLocation.updated_at,
                UiDialogSession.flow_id,
                UiDialogSession.flow_version,
                UiDialogSession.node_id,
                UiDialogSession.status,
                delivery.label("delivery_status"),
            )
            .outerjoin(UiDialogSession, UiDialogSession.id == UiUserLocation.session_id)
            .where(UiUserLocation.user_id.in_(user_ids))
        )
        rows = (await self._session.execute(query)).all()
        return [
            LocationInfo(
                row.user_id,
                row.chat_id,
                row.flow_id,
                row.flow_version,
                row.node_id,
                cast(SessionStatus | None, row.status),
                cast(DeliveryStatus | None, row.delivery_status),
                row.updated_at,
                cast(Literal["runtime", "legacy", "unknown"], row.owner),
                row.legacy_state,
                row.handler,
            )
            for row in rows
        ]

    async def transitions(self, user_id: int, before: int | None, limit: int) -> list[TransitionInfo]:
        query = select(UiUserTransition).where(UiUserTransition.user_id == user_id)
        if before is not None:
            query = query.where(UiUserTransition.id < before)
        rows = await self._session.scalars(query.order_by(UiUserTransition.id.desc()).limit(limit))
        return [
            TransitionInfo(
                id=row.id,
                flow_id=row.flow_id,
                from_step=row.from_step,
                to_step=row.to_step,
                outcome=row.outcome,
                occurred_at=row.occurred_at,
                owner=cast(Literal["runtime", "legacy", "unknown"], row.owner),
                flow_version=row.flow_version,
            )
            for row in rows
        ]
