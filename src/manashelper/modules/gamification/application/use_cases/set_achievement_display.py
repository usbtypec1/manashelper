from dataclasses import dataclass

from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS, AchievementDisplay
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


@dataclass(frozen=True, slots=True)
class SetAchievementDisplayUseCase:
    repository: AchievementRepository

    async def execute(self, key: str, display: AchievementDisplay) -> bool:
        if key not in ACHIEVEMENT_KEYS:
            return False
        await self.repository.save_display(key, display)
        return True
