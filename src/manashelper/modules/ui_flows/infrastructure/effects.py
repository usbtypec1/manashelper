import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.orm import UiScreenDelivery
from ui_flows.domain.contracts import DelegateResult
from ui_flows.domain.effects import EffectStatus, ExternalOperation
from ui_flows.errors import FlowConflictError


def _operation(row: UiExternalOperation) -> ExternalOperation:
    return ExternalOperation(
        id=row.id,
        session_id=row.session_id,
        user_id=row.user_id,
        chat_id=row.chat_id,
        revision=row.revision,
        flow_id=row.flow_id,
        flow_version=row.flow_version,
        node_id=row.node_id,
        delegate_id=row.delegate_id,
        contract_version=row.contract_version,
        arguments=dict(row.arguments),
        status=cast(EffectStatus, row.status),
        result=DelegateResult(row.result["outcome"], dict(row.result["values"])) if row.result is not None else None,
        error_code=row.error_code,
        created_at=row.created_at,
    )


class EffectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def atomic(self) -> AsyncIterator[None]:
        async with self._session.begin_nested():
            yield

    async def prepare(self, operation: ExternalOperation) -> ExternalOperation:
        await self._session.execute(
            insert(UiExternalOperation)
            .values(
                id=operation.id,
                session_id=operation.session_id,
                user_id=operation.user_id,
                chat_id=operation.chat_id,
                revision=operation.revision,
                flow_id=operation.flow_id,
                flow_version=operation.flow_version,
                node_id=operation.node_id,
                delegate_id=operation.delegate_id,
                contract_version=operation.contract_version,
                arguments=dict(operation.arguments),
                status="pending",
            )
            .on_conflict_do_nothing(constraint="uq_ui_external_position")
        )
        row = await self._session.scalar(
            select(UiExternalOperation)
            .where(
                UiExternalOperation.session_id == operation.session_id,
                UiExternalOperation.revision == operation.revision,
                UiExternalOperation.node_id == operation.node_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise FlowConflictError("External operation preparation conflicted")
        if (
            row.user_id,
            row.chat_id,
            row.flow_id,
            row.flow_version,
            row.delegate_id,
            row.contract_version,
            row.arguments,
        ) != (
            operation.user_id,
            operation.chat_id,
            operation.flow_id,
            operation.flow_version,
            operation.delegate_id,
            operation.contract_version,
            operation.arguments,
        ):
            raise FlowConflictError("The position already belongs to another external operation")
        return _operation(row)

    async def get(self, operation_id: UUID, *, lock: bool = False) -> ExternalOperation | None:
        row = await self._row(operation_id, lock=lock)
        return _operation(row) if row is not None else None

    async def _row(self, operation_id: UUID, *, lock: bool) -> UiExternalOperation | None:
        query = (
            select(UiExternalOperation)
            .where(UiExternalOperation.id == operation_id)
            .execution_options(populate_existing=True)
        )
        row: UiExternalOperation | None = await self._session.scalar(query.with_for_update() if lock else query)
        return row

    async def claim(self, operation_id: UUID) -> ExternalOperation | None:
        row = await self._row(operation_id, lock=True)
        if row is None or row.status != "pending":
            return None
        row.status = "unknown"
        await self._session.flush()
        return _operation(row)

    async def complete(self, operation_id: UUID, result: DelegateResult) -> bool:
        row = await self._row(operation_id, lock=True)
        if row is None or row.status != "unknown":
            return False
        row.result = {"outcome": result.outcome, "values": dict(result.values)}
        row.status = "succeeded"
        await self._session.flush()
        return True

    async def fail(self, operation_id: UUID, error_code: str) -> bool:
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", error_code) is None:
            raise ValueError("External operation error requires a stable code")
        row = await self._row(operation_id, lock=True)
        if row is None or row.status != "unknown":
            return False
        row.error_code = error_code
        row.status = "failed"
        await self._session.flush()
        return True

    async def mark_applied(self, operation_id: UUID) -> bool:
        row = await self._row(operation_id, lock=True)
        if row is None or row.status != "succeeded":
            return False
        row.status = "applied"
        await self._session.flush()
        return True

    async def pending(self, limit: int = 100) -> list[UUID]:
        if not 1 <= limit <= 100:
            raise ValueError("External operation batch must contain 1 to 100 items")
        return list(
            await self._session.scalars(
                select(UiExternalOperation.id)
                # A recorded result can be applied after restart without repeating external I/O.
                .where(
                    or_(
                        UiExternalOperation.status.in_(("pending", "succeeded")),
                        (UiExternalOperation.status == "applied")
                        & exists(
                            select(UiScreenDelivery.token).where(
                                UiScreenDelivery.operation_id == UiExternalOperation.id,
                                UiScreenDelivery.status == "pending",
                            )
                        ),
                    )
                )
                .order_by(UiExternalOperation.created_at, UiExternalOperation.id)
                .limit(limit)
            )
        )

    async def put_secret(
        self,
        secret_id: UUID,
        session_id: UUID,
        user_id: int,
        chat_id: int,
        ciphertext: str,
        expires_at: datetime,
    ) -> None:
        self._session.add(
            UiInputSecret(
                id=secret_id,
                session_id=session_id,
                user_id=user_id,
                chat_id=chat_id,
                ciphertext=ciphertext,
                expires_at=expires_at,
            )
        )
        await self._session.flush()

    async def get_secret(
        self, secret_id: UUID, session_id: UUID, user_id: int, chat_id: int, now: datetime
    ) -> str | None:
        ciphertext: str | None = await self._session.scalar(
            select(UiInputSecret.ciphertext).where(
                UiInputSecret.id == secret_id,
                UiInputSecret.session_id == session_id,
                UiInputSecret.user_id == user_id,
                UiInputSecret.chat_id == chat_id,
                UiInputSecret.expires_at > now,
            )
        )
        return ciphertext

    async def remove_secret(self, secret_id: UUID) -> None:
        await self._session.execute(delete(UiInputSecret).where(UiInputSecret.id == secret_id))

    async def purge_expired(self, now: datetime) -> int:
        removed = await self._session.scalars(
            delete(UiInputSecret).where(UiInputSecret.expires_at <= now).returning(UiInputSecret.id)
        )
        return len(list(removed))
