from collections.abc import AsyncIterator
from typing import Protocol

from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.tracking import EdersEvent


class EdersNotificationSender(Protocol):
    def send(self, user_id: int, locale: Locale, events: list[EdersEvent]) -> AsyncIterator[EdersEvent]:
        """Yield each event after its message has been accepted into the outbox."""
        ...
