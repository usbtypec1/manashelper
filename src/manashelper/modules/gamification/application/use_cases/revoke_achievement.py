from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS
from manashelper.modules.gamification.application.notifications import AchievementNotificationSender
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.users.application.queries import UsersQuery

RevokeResult = Literal["revoked", "not_awarded", "missing"]


@dataclass(frozen=True, slots=True)
class RevokeAchievementUseCase:
    repository: AchievementRepository
    notifications: AchievementNotificationSender
    users: UsersQuery

    async def execute(self, user_id: int, key: str) -> RevokeResult:
        if key not in ACHIEVEMENT_KEYS or not await self.users.exists(user_id):
            return "missing"
        if not await self.repository.revoke(user_id, key, datetime.now(UTC)):
            return "not_awarded"
        await self.notifications.cancel(user_id, key)
        return "revoked"
