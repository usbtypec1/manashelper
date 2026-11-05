from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.core.config import Settings
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


@dataclass(frozen=True, slots=True)
class GrantPokemonUseCase:
    repository: AchievementRepository
    settings: Settings

    async def execute(self, user_id: int, *, admin_chat_id: int, actor_id: int) -> bool:
        if admin_chat_id != self.settings.admin_chat_id:
            raise PermissionError("Only the configured admin chat can grant achievements")
        if await self.repository.lock_progress(user_id) is None:
            raise LookupError("User is not registered")
        return await self.repository.award(user_id, "pokemon", datetime.now(UTC), actor_id)
