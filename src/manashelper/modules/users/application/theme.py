from dataclasses import dataclass

from manashelper.localization.theme import Theme
from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class ThemeQuery:
    user_repository: UserRepository

    async def get_theme(self, user_id: int) -> Theme:
        user = await self.user_repository.get_by_id(user_id)
        return Theme(user.theme) if user is not None and user.theme is not None else Theme.BASIC
