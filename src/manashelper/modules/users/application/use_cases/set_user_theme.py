from dataclasses import dataclass

from manashelper.localization.theme import Theme
from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class SetUserThemeUseCase:
    user_repository: UserRepository

    async def execute(self, user_id: int, theme: Theme) -> None:
        await self.user_repository.set_theme(user_id, theme.value)
