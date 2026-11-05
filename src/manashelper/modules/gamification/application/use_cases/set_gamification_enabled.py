from dataclasses import dataclass

from manashelper.core.config import Settings
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


@dataclass(frozen=True, slots=True)
class SetGamificationEnabledUseCase:
    repository: AchievementRepository
    settings: Settings

    async def execute(self, user_id: int, enabled: bool, *, admin_chat_id: int) -> None:
        if admin_chat_id != self.settings.admin_chat_id:
            raise PermissionError("Only the configured admin chat can manage achievement access")
        await self.repository.set_enabled(user_id, enabled)
