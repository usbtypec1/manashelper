from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

from aiogram.methods import SendMessage
from aiogram.types import LinkPreviewOptions

from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.tracking import EdersEvent
from manashelper.modules.eders.presentation.formatter import format_eders_event, format_material_events
from manashelper.modules.users.application.theme import ThemeQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.outbox.service import OutboxService


class TelegramEdersNotificationSender:
    def __init__(self, outbox: OutboxService, themes: ThemeQuery) -> None:
        self._outbox = outbox
        self._themes = themes

    async def send(self, user_id: int, locale: Locale, events: list[EdersEvent]) -> AsyncIterator[EdersEvent]:
        theme = await self._themes.get_theme(user_id)
        with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
            materials = [event for event in events if event.event_type.startswith("material_")]
            messages = format_material_events(materials)
            messages.extend(
                (format_eders_event(event), [event]) for event in events if not event.event_type.startswith("material_")
            )
        for text, batch in messages:
            expiry = datetime.now(UTC) + timedelta(days=1)
            for event in batch:
                if not event.event_type.startswith("material_") and event.activity.closes.instant:
                    expiry = min(expiry, event.activity.closes.instant)
            accepted = await self._outbox.enqueue(
                user_id,
                [SendMessage(chat_id=user_id, text=text, link_preview_options=LinkPreviewOptions(is_disabled=True))],
                expires_at=expiry,
                source_keys=[event.key for event in batch],
            )
            if not accepted:
                continue
            for event in batch:
                yield event
