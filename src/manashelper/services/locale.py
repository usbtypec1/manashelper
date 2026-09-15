from manashelper.localization.locale import Locale, resolve_from_language_code
from manashelper.repositories.user_repository import UserRepository


class LocaleService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def resolve(
        self,
        user_id: int,
        full_name: str,
        username: str | None,
        language_code: str | None,
    ) -> Locale | None:
        """Upsert the user and return their resolved locale.

        A user's explicitly-saved locale always wins. Otherwise, this auto-detects and saves
        the locale from the Telegram client's language, returning None when that can't be
        mapped to a supported locale either, so the caller can ask the user to pick one.
        """
        user = await self._user_repository.upsert(user_id=user_id, full_name=full_name, username=username)
        if user.locale is not None:
            return Locale(user.locale)

        detected = resolve_from_language_code(language_code)
        if detected is not None:
            user.locale = detected.value
        return detected

    async def set_locale(self, user_id: int, locale: Locale) -> None:
        await self._user_repository.set_locale(user_id, locale.value)
