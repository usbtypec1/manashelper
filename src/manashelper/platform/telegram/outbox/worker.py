import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramRetryAfter, TelegramServerError

from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.users.application.use_cases.stop_bot_delivery import StopBotDeliveryUseCase
from manashelper.platform.telegram.delivery import is_permanent_recipient_error
from manashelper.platform.telegram.outbox.models import OutboxMessage
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import METHOD_TYPES, OutgoingMethod, is_night

logger = logging.getLogger(__name__)
MAX_FAILURES = 12
LEASE_SECONDS = 60
REQUEST_TIMEOUT = 20


@dataclass(frozen=True, slots=True)
class ClaimedMessage:
    id: int
    token: UUID
    method: OutgoingMethod
    expires_at: datetime


def retry_delay(failures: int) -> float:
    ceiling = min(300.0, 2.0 ** min(failures, 9))
    return random.uniform(ceiling / 2.0, ceiling)


def finish(message: OutboxMessage, status: str, now: datetime) -> None:
    message.status = status
    message.finished_at = now
    message.lease_token = None
    message.locked_until = None


class OutboxWorker:
    def __init__(
        self,
        repository: OutboxRepository,
        stop_bot_delivery: StopBotDeliveryUseCase,
        recipients: NotificationRecipientsQuery,
    ) -> None:
        self._repository = repository
        self._stop_bot_delivery = stop_bot_delivery
        self._recipients = recipients

    async def claim(self, bot_id: int, now: datetime) -> ClaimedMessage | None:
        # Each claim commits before any HTTP request. A crashed worker's lease
        # expires; the row can then be recovered by any process using SKIP LOCKED.
        for _ in range(50):
            row = await self._repository.next_message(now)
            if row is None:
                return None
            if row.expires_at <= now:
                finish(row, "expired", now)
                continue
            if not await self._recipients.allows_queued_delivery(row.user_id, row.category, now):
                finish(row, "cancelled", now)
                continue
            delay = await self._repository.reserve(bot_id, row.user_id, now)
            if delay > 0:
                row.status = "pending"
                row.lease_token = None
                row.locked_until = None
                row.available_at = now + timedelta(seconds=delay)
                continue
            try:
                payload = row.methods[row.position]
                method = METHOD_TYPES[payload["method"]].model_validate(payload["data"])
            except (KeyError, IndexError, ValueError, TypeError):
                row.last_error = "invalid_payload"
                finish(row, "failed", now)
                continue
            if is_night(now):
                method.disable_notification = True
                # Replace the JSON value for SQLAlchemy change tracking. Keep the
                # flag for retries and every remaining part, even after morning.
                row.methods = [
                    {**part, "data": {**part["data"], "disable_notification": True}}
                    if position >= row.position
                    else part
                    for position, part in enumerate(row.methods)
                ]
            row.status = "processing"
            row.lease_token = uuid4()
            row.locked_until = now + timedelta(seconds=LEASE_SECONDS)
            row.attempts += 1
            return ClaimedMessage(row.id, row.lease_token, method, row.expires_at)
        return None

    async def complete(self, claim: ClaimedMessage, now: datetime) -> None:
        row = await self._repository.get_locked(claim.id)
        if row is None or row.status != "processing" or row.lease_token != claim.token:
            return
        row.position += 1
        row.failures = 0
        row.last_error = None
        row.lease_token = None
        row.locked_until = None
        row.available_at = now
        if row.position == len(row.methods):
            finish(row, "sent", now)
        else:
            row.status = "pending"

    async def fail(self, claim: ClaimedMessage, error: Exception, bot_id: int, now: datetime) -> None:
        row = await self._repository.get_locked(claim.id)
        if row is None or row.status != "processing" or row.lease_token != claim.token:
            return
        # Do not persist Telegram descriptions, payloads or URLs containing bot tokens.
        row.last_error = type(error).__name__[:64]
        delay: float | None = None
        if isinstance(error, TelegramRetryAfter):
            cooldown = max(1, error.retry_after)
            await self._repository.pause(bot_id, now + timedelta(seconds=cooldown), now)
            # Give other chats a turn after the shared cooldown. Otherwise the
            # same chat can hit a local flood limit and indefinitely starve them.
            delay = cooldown + 1.0 + random.uniform(0.0, 1.0)
        elif isinstance(error, (TelegramServerError, TelegramNetworkError)):
            row.failures += 1
            if row.failures < MAX_FAILURES:
                delay = retry_delay(row.failures)
        elif isinstance(error, TelegramAPIError) and is_permanent_recipient_error(error):
            await self._stop_bot_delivery.execute(row.user_id)
        if delay is None:
            finish(row, "failed", now)
            logger.warning("Outbox message %s failed: %s", row.id, row.last_error)
        elif now + timedelta(seconds=delay) >= row.expires_at:
            finish(row, "expired", now)
        else:
            row.status = "pending"
            row.lease_token = None
            row.locked_until = None
            row.available_at = now + timedelta(seconds=delay)

    async def expire(self, claim: ClaimedMessage, now: datetime) -> None:
        row = await self._repository.get_locked(claim.id)
        if row and row.status == "processing" and row.lease_token == claim.token:
            finish(row, "expired", now)

    async def cleanup(self) -> None:
        await self._repository.cleanup(datetime.now(UTC))
