from dataclasses import dataclass
from typing import Protocol

from manashelper.modules.notifications.queries import NotificationRecipientsQuery


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    sent: int
    total: int


class BroadcastSender(Protocol):
    async def send(self, user_id: int, body: str) -> bool: ...


class SendBroadcast:
    def __init__(self, recipients: NotificationRecipientsQuery) -> None:
        self._recipients = recipients

    async def execute(self, body: str, sender: BroadcastSender) -> BroadcastResult:
        recipient_ids = await self._recipients.for_broadcasts()
        sent_count = 0
        for user_id in recipient_ids:
            if await sender.send(user_id, body):
                sent_count += 1
        return BroadcastResult(sent=sent_count, total=len(recipient_ids))
