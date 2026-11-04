from dataclasses import dataclass

from manashelper.modules.eders.application.tracking import (
    EdersSetting,
    EdersSettings,
    get_eders_settings,
)
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.outbox.service import OutboxService


@dataclass(frozen=True, slots=True)
class ToggleEdersSettingUseCase:
    eders_repository: EdersRepository
    users: UsersQuery
    outbox: OutboxService

    async def execute(self, user_id: int, setting: EdersSetting) -> EdersSettings:
        await get_eders_settings(self.eders_repository, self.users, user_id)
        state = await self.eders_repository.get_state(user_id)
        setattr(state, setting.value, not getattr(state, setting.value))
        if not getattr(state, setting.value):
            event_types = {
                EdersSetting.DAY_BEFORE: {"before_24"},
                EdersSetting.TWO_HOURS_BEFORE: {"before_2"},
                EdersSetting.OPENINGS: {"opened"},
                EdersSetting.DEADLINE_CHANGES: {"changed"},
                EdersSetting.NEW_MATERIALS: {"material_new", "material_changed"},
            }.get(setting, set())
            rows = await self.eders_repository.get_notifications(user_id)
            await self.outbox.cancel_sources([row.event_key for row in rows if row.event_type in event_types])
        return EdersSettings(*(getattr(state, item.value) for item in EdersSetting))
