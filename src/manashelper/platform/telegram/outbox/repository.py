from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import BigInteger, and_, any_, cast, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from manashelper.platform.telegram.outbox.models import OutboxMessage, OutboxRateBucket
from manashelper.platform.telegram.outbox.rate_limit import CHAT_BUCKET, GLOBAL_BUCKET, GROUP_BUCKET, TokenBucket

RETRYABLE_STATUSES = ("failed", "expired", "cancelled")
ACTIVE_STATUSES = ("pending", "processing")


def _recipient_queue_head() -> ColumnElement[bool]:
    earlier = aliased(OutboxMessage)
    return and_(
        OutboxMessage.status.in_(ACTIVE_STATUSES),
        ~exists().where(
            earlier.user_id == OutboxMessage.user_id,
            earlier.id < OutboxMessage.id,
            earlier.status.in_(ACTIVE_STATUSES),
        ),
    )


@dataclass(frozen=True, slots=True)
class BatchDelivery:
    user_id: int
    status: str
    attempts: int
    last_error: str | None


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: OutboxMessage) -> bool:
        values = {
            "user_id": message.user_id,
            "category": message.category,
            "methods": message.methods,
            "source_keys": message.source_keys,
            "deduplication_key": message.deduplication_key,
            "created_at": message.created_at,
            "available_at": message.available_at,
            "expires_at": message.expires_at,
        }
        statement = insert(OutboxMessage).values(**values).on_conflict_do_nothing().returning(OutboxMessage.id)
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    def add_batch(self, messages: list[OutboxMessage]) -> None:
        self._session.add_all(messages)

    async def batch_counts(self, batch_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
        if not batch_ids:
            return {}
        result = await self._session.execute(
            select(OutboxMessage.batch_id, OutboxMessage.status, func.count())
            .where(OutboxMessage.batch_id.in_(batch_ids))
            .group_by(OutboxMessage.batch_id, OutboxMessage.status)
        )
        counts: dict[UUID, dict[str, int]] = {}
        for batch_id, status, count in result.tuples():
            if batch_id is not None:
                counts.setdefault(batch_id, {})[status] = count
        return counts

    async def batch_deliveries(self, batch_id: UUID, *, after: int | None, limit: int) -> list[BatchDelivery]:
        statement = (
            select(OutboxMessage.user_id, OutboxMessage.status, OutboxMessage.attempts, OutboxMessage.last_error)
            .where(OutboxMessage.batch_id == batch_id)
            .order_by(OutboxMessage.user_id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(OutboxMessage.user_id > after)
        result = await self._session.execute(statement)
        return [BatchDelivery(*row) for row in result.tuples()]

    async def retry_batch(self, batch_id: UUID, user_ids: list[int], now: datetime) -> int:
        if not user_ids:
            return 0
        statement = (
            update(OutboxMessage)
            .where(
                OutboxMessage.batch_id == batch_id,
                OutboxMessage.status.in_(RETRYABLE_STATUSES),
                OutboxMessage.user_id == any_(cast(user_ids, ARRAY(BigInteger))),
            )
            .values(
                status="pending",
                available_at=now,
                expires_at=now + timedelta(days=1),
                failures=0,
                finished_at=None,
                lease_token=None,
                locked_until=None,
                last_error=None,
            )
            .returning(OutboxMessage.id)
        )
        return len((await self._session.scalars(statement)).all())

    async def next_messages(self, now: datetime, limit: int) -> list[OutboxMessage]:
        statement = (
            select(OutboxMessage)
            .where(
                _recipient_queue_head(),
                or_(OutboxMessage.available_at <= now, OutboxMessage.expires_at <= now),
                or_(OutboxMessage.locked_until.is_(None), OutboxMessage.locked_until <= now),
            )
            .order_by(OutboxMessage.available_at, OutboxMessage.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(await self._session.scalars(statement))

    async def next_attempt_at(self) -> datetime | None:
        # PostgreSQL's GREATEST ignores a NULL locked_until.
        ready_at: ColumnElement[datetime] = func.greatest(
            func.least(OutboxMessage.available_at, OutboxMessage.expires_at),
            OutboxMessage.locked_until,
            type_=OutboxMessage.available_at.type,
        )
        next_at: datetime | None = await self._session.scalar(select(func.min(ready_at)).where(_recipient_queue_head()))
        return next_at

    async def get_locked(self, message_id: int) -> OutboxMessage | None:
        return await self._session.get(OutboxMessage, message_id, with_for_update=True, populate_existing=True)

    async def _bucket(self, key: str, policy: TokenBucket, now: datetime) -> OutboxRateBucket:
        await self._session.execute(
            insert(OutboxRateBucket).values(key=key, tokens=policy.capacity, updated_at=now).on_conflict_do_nothing()
        )
        return (
            await self._session.execute(select(OutboxRateBucket).where(OutboxRateBucket.key == key).with_for_update())
        ).scalar_one()

    async def reserve(self, bot_id: int, user_id: int, now: datetime) -> float:
        policies = (GLOBAL_BUCKET, CHAT_BUCKET if user_id > 0 else GROUP_BUCKET)
        rows = (
            await self._bucket(f"bot:{bot_id}", policies[0], now),
            await self._bucket(f"bot:{bot_id}:chat:{user_id}", policies[1], now),
        )
        delay = 0.0
        for row, policy in zip(rows, policies, strict=True):
            row.tokens = policy.refill(row.tokens, row.updated_at, now)
            row.updated_at = max(row.updated_at, now)
            delay = max(delay, policy.delay(row.tokens))
            if row.blocked_until:
                delay = max(delay, (row.blocked_until - now).total_seconds())
        if delay <= 0:
            for row in rows:
                row.tokens -= 1.0
        return max(0.0, delay)

    async def pause(self, bot_id: int, until: datetime, now: datetime) -> None:
        row = await self._bucket(f"bot:{bot_id}", GLOBAL_BUCKET, now)
        row.blocked_until = max(row.blocked_until or until, until)
        # A flood-control pause must not produce a burst when it ends.
        row.tokens = 0.0
        row.updated_at = max(row.updated_at, until)

    async def cancel_sources(self, keys: list[str], now: datetime) -> None:
        if not keys:
            return
        await self._session.execute(
            update(OutboxMessage)
            .where(
                OutboxMessage.status == "pending",
                or_(*(OutboxMessage.source_keys.contains([key]) for key in keys)),
            )
            .values(status="cancelled", finished_at=now)
        )

    async def cleanup(self, now: datetime) -> None:
        await self._session.execute(
            update(OutboxMessage)
            .where(
                OutboxMessage.status.in_(("pending", "processing")),
                OutboxMessage.expires_at <= now,
                or_(OutboxMessage.locked_until.is_(None), OutboxMessage.locked_until <= now),
            )
            .values(status="expired", finished_at=now, lease_token=None, locked_until=None)
        )
        await self._session.execute(
            delete(OutboxMessage).where(
                OutboxMessage.batch_id.is_(None), OutboxMessage.finished_at <= now - timedelta(days=1)
            )
        )
        await self._session.execute(
            delete(OutboxRateBucket).where(
                OutboxRateBucket.key.like("%:chat:%"),
                OutboxRateBucket.updated_at < now - timedelta(days=1),
                or_(OutboxRateBucket.blocked_until.is_(None), OutboxRateBucket.blocked_until < now),
            )
        )
