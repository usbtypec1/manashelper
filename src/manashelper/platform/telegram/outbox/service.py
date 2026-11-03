import hashlib
import json
from datetime import UTC, datetime, timedelta

from aiogram.methods import SendMessage, SendPhoto, SendRichMessage

from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.platform.telegram.outbox.models import OutboxMessage
from manashelper.platform.telegram.outbox.repository import OutboxRepository

type OutgoingMethod = SendMessage | SendPhoto | SendRichMessage
METHOD_TYPES: dict[str, type[OutgoingMethod]] = {
    "sendMessage": SendMessage,
    "sendPhoto": SendPhoto,
    "sendRichMessage": SendRichMessage,
}


class OutboxService:
    def __init__(self, repository: OutboxRepository, status: BotStatusService) -> None:
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
        payload = []
        for method in methods:
            if method.chat_id != user_id:
                raise ValueError("Outbox methods must target their recipient")
            # Excluding defaults removes aiogram's runtime Default sentinels. Only
            # reusable file IDs and URLs are supported; binary uploads fail JSON encoding.
            data = method.model_dump(mode="json", exclude_defaults=True)
            if not isinstance(method, SendRichMessage):
                data.setdefault("parse_mode", "HTML")
            payload.append({"method": method.__api_method__, "data": data})
        if source_keys and deduplication_key is None:
            identity = json.dumps([user_id, sorted(source_keys), payload], sort_keys=True, ensure_ascii=False)
            deduplication_key = hashlib.sha256(identity.encode()).hexdigest()
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

    async def cancel_sources(self, keys: list[str]) -> None:
        await self._repository.cancel_sources(keys, datetime.now(UTC))
