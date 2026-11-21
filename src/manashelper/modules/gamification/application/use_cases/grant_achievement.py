from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS
from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.users.application.queries import UsersQuery

GrantResult = Literal["granted", "already_granted", "unavailable", "missing"]


@dataclass(frozen=True, slots=True)
class GrantAchievementUseCase:
    awards: AwardAchievementUseCase
    gamification: GamificationQuery
    users: UsersQuery

    async def execute(self, user_id: int, key: str, *, granted_by: int) -> GrantResult:
        if key not in ACHIEVEMENT_KEYS or not await self.users.exists(user_id):
            return "missing"
        if await self.users.is_blocked(user_id):
            return "unavailable"
        if await self.awards.execute(user_id, key, datetime.now(UTC), granted_by=granted_by):
            return "granted"
        if await self.gamification.is_enabled(user_id) and await self.gamification.has_award(user_id, key):
            return "already_granted"
        return "unavailable"
