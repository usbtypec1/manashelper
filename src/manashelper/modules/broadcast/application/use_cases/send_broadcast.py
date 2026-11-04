from dataclasses import dataclass

from manashelper.modules.broadcast.service import BroadcastResult, BroadcastSender
from manashelper.modules.notifications.queries import NotificationRecipientsQuery


@dataclass(frozen=True, slots=True)
class SendBroadcastUseCase:
    recipients: NotificationRecipientsQuery

    async def execute(self, body: str, sender: BroadcastSender) -> BroadcastResult:
        recipient_ids = await self.recipients.for_broadcasts()
        sent_count = 0
        for user_id in recipient_ids:
            if await sender.send(user_id, body):
                sent_count += 1
        return BroadcastResult(sent=sent_count, total=len(recipient_ids))
