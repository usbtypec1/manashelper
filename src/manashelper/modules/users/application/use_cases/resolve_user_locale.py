from dataclasses import dataclass

from manashelper.localization.locale import Locale, resolve_from_language_code
from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class ResolveUserLocaleUseCase:
    user_repository: UserRepository

    async def execute(
        self, user_id: int, full_name: str, username: str | None, language_code: str | None, *, resume_bot: bool = False
    ) -> Locale:
        """Upsert the user and return their resolved locale.

        A user's explicitly-saved locale always wins. Otherwise, this auto-detects and saves
        the locale from the Telegram client's language, falling back to `DEFAULT_LOCALE` when
        that language isn't one of the supported locales.
        """
        user = await self.user_repository.upsert(user_id=user_id, full_name=full_name, username=username)
        if resume_bot:
            user.bot_stopped = False
        if user.locale is not None:
            return Locale(user.locale)
        detected = resolve_from_language_code(language_code)
        user.locale = detected.value
        return detected
