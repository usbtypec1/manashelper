from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.eders.application.polling import EdersNotificationSender
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.refresh_eders_snapshot import RefreshEdersSnapshotUseCase
from manashelper.modules.users.application.locale import LocaleQuery


@dataclass(frozen=True, slots=True)
class PollEdersUserUseCase:
    refresh_eders_snapshot: RefreshEdersSnapshotUseCase
    tracking: EdersTrackingService
    locales: LocaleQuery

    async def execute(self, user_id: int, sender: EdersNotificationSender) -> None:
        await self.refresh_eders_snapshot.execute(user_id)
        locale = await self.locales.get_locale(user_id)
        events = await self.tracking.pending_events(user_id, datetime.now(UTC))
        async for event in sender.send(user_id, locale, events):
            await self.tracking.mark_sent(user_id, event.key, datetime.now(UTC))
