from dataclasses import dataclass

from manashelper.localization.locale import DEFAULT_LOCALE, Locale
from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class LocaleQuery:
    user_repository: UserRepository

    async def get_locale(self, user_id: int) -> Locale:
        """Read a user's saved locale without upserting them, falling back to `DEFAULT_LOCALE`.

        Used by delivery adapters and jobs notifying a different chat than the current update.
        """
        user = await self.user_repository.get_by_id(user_id)
        if user is not None and user.locale is not None:
            return Locale(user.locale)
        return DEFAULT_LOCALE
