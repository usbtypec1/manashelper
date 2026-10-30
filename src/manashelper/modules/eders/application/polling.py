from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Protocol

from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.tracking import EdersEvent, EdersTrackingService
from manashelper.modules.users.application.locale import LocaleService


class EdersNotificationSender(Protocol):
    def send(self, user_id: int, locale: Locale, events: list[EdersEvent]) -> AsyncIterator[EdersEvent]:
        """Yield each event only after its message has been delivered."""
        ...


class PollEdersUser:
    def __init__(self, service: EdersService, tracking: EdersTrackingService, locales: LocaleService) -> None:
        self._service = service
        self._tracking = tracking
        self._locales = locales

    async def execute(self, user_id: int, sender: EdersNotificationSender) -> None:
        await self._service.refresh_snapshot(user_id)
        locale = await self._locales.get_locale(user_id)
        events = await self._tracking.pending_events(user_id, datetime.now(UTC))
        async for event in sender.send(user_id, locale, events):
            await self._tracking.mark_sent(user_id, event.key, datetime.now(UTC))
