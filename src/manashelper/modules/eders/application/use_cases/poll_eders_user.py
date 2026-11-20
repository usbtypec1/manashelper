from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.eders.application.polling import EdersNotificationSender
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.refresh_eders_snapshot import RefreshEdersSnapshotUseCase
from manashelper.modules.obis.errors import ObisManualLoginRequiredError, ObisRetryLaterError
from manashelper.modules.users.application.locale import LocaleQuery


@dataclass(frozen=True, slots=True)
class PollEdersUserUseCase:
    refresh_eders_snapshot: RefreshEdersSnapshotUseCase
    tracking: EdersTrackingService
    locales: LocaleQuery

    async def execute(self, user_id: int, sender: EdersNotificationSender) -> None:
        try:
            await self.refresh_eders_snapshot.execute(user_id)
        except (ObisManualLoginRequiredError, ObisRetryLaterError):
            # Preserve auth state; OBIS polling queues the one-time login notice.
            return
        locale = await self.locales.get_locale(user_id)
        events = await self.tracking.pending_events(user_id, datetime.now(UTC))
        sent_keys = [event.key async for event in sender.send(user_id, locale, events)]
        if sent_keys:
            await self.tracking.mark_sent(user_id, sent_keys, datetime.now(UTC))
