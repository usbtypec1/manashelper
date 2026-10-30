from manashelper.localization.theme import Theme
from manashelper.modules.users.infrastructure.user_repository import UserRepository


class ThemeService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def get_theme(self, user_id: int) -> Theme:
        user = await self._user_repository.get_by_id(user_id)
        return Theme(user.theme) if user is not None and user.theme is not None else Theme.BASIC

    async def set_theme(self, user_id: int, theme: Theme) -> None:
        await self._user_repository.set_theme(user_id, theme.value)
