from dataclasses import dataclass
from datetime import datetime

from manashelper.modules.gamification.application.notifications import AchievementNotificationSender
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


@dataclass(frozen=True, slots=True)
class AwardAchievementUseCase:
    repository: AchievementRepository
    notifications: AchievementNotificationSender

    async def execute(self, user_id: int, key: str, now: datetime) -> None:
        # The award and notification share the caller's request transaction.
        if await self.repository.award(user_id, key, now):
            await self.notifications.earned(user_id, key)
