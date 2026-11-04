from dataclasses import dataclass

from manashelper.localization.locale import Locale
from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class SetUserLocaleUseCase:
    user_repository: UserRepository

    async def execute(self, user_id: int, locale: Locale) -> None:
        await self.user_repository.set_locale(user_id, locale.value)
