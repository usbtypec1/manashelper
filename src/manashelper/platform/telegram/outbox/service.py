import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from aiogram.methods import SendMessage, SendPhoto, SendRichMessage

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.users.application.bot_status import BotStatusQuery
from manashelper.platform.telegram.outbox.models import OutboxMessage
from manashelper.platform.telegram.outbox.repository import OutboxRepository

type OutgoingMethod = SendMessage | SendPhoto | SendRichMessage
METHOD_TYPES: dict[str, type[OutgoingMethod]] = {
    "sendMessage": SendMessage,
    "sendPhoto": SendPhoto,
    "sendRichMessage": SendRichMessage,
}


def is_night(now: datetime) -> bool:
    hour = now.astimezone(BISHKEK_TZ).hour
    return hour >= 22 or hour < 8


def _method_payload(user_id: int, method: OutgoingMethod) -> dict[str, Any]:
    if method.chat_id != user_id:
        raise ValueError("Outbox methods must target their recipient")
    # Excluding defaults removes aiogram's runtime Default sentinels.
    data = method.model_dump(mode="json", exclude_defaults=True)
    if not isinstance(method, SendRichMessage):
        data.setdefault("parse_mode", "HTML")
    return {"method": method.__api_method__, "data": data}


def _apply_quiet_hours(payload: list[dict[str, Any]], now: datetime) -> None:
    for part in payload:
        part["data"]["disable_notification"] = is_night(now) or bool(part["data"].get("disable_notification"))


class OutboxService:
    def __init__(self, repository: OutboxRepository, status: BotStatusQuery) -> None:
        self._repository = repository
        self._status = status

    async def enqueue(
        self,
        user_id: int,
        methods: list[OutgoingMethod],
        *,
        expires_at: datetime | None = None,
        deduplication_key: str | None = None,
        source_keys: list[str] | None = None,
        category: str = "notification",
    ) -> bool:
        now = datetime.now(UTC)
        expires_at = expires_at or now + timedelta(days=1)
        if expires_at.tzinfo is None:
            raise ValueError("Outbox expiration must include a timezone")
        if not methods or expires_at <= now or await self._status.is_stopped(user_id):
            return False
        payload = [_method_payload(user_id, method) for method in methods]
        if source_keys and deduplication_key is None:
            identity = json.dumps([user_id, sorted(source_keys), payload], sort_keys=True, ensure_ascii=False)
            deduplication_key = hashlib.sha256(identity.encode()).hexdigest()
        # Apply the delivery policy after computing the source identity, so a
        # retry across the day/night boundary cannot enqueue the same event twice.
        _apply_quiet_hours(payload, now)
        added = await self._repository.add(
            OutboxMessage(
                user_id=user_id,
                category=category,
                methods=payload,
                source_keys=source_keys or [],
                deduplication_key=deduplication_key,
                created_at=now,
                available_at=now,
                expires_at=expires_at,
            )
        )
        # An existing deduplication key is already durably accepted in this transaction.
        return added or deduplication_key is not None

    def enqueue_batch(
        self, batch_id: UUID, deliveries: Iterable[tuple[int, list[OutgoingMethod]]], *, category: str
    ) -> None:
        """Queue deliveries for recipients selected by the caller's eligibility query."""
        now = datetime.now(UTC)
        messages = []
        for user_id, methods in deliveries:
            payload = [_method_payload(user_id, method) for method in methods]
            _apply_quiet_hours(payload, now)
            messages.append(
                OutboxMessage(
                    batch_id=batch_id,
                    user_id=user_id,
                    category=category,
                    methods=payload,
                    source_keys=[],
                    created_at=now,
                    available_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        self._repository.add_batch(messages)

    async def cancel_sources(self, keys: list[str]) -> None:
        await self._repository.cancel_sources(keys, datetime.now(UTC))
