from dataclasses import dataclass

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.browser_login import EdersLoginTokens, browser_login_marker
from manashelper.modules.eders.errors import EdersFetchError
from manashelper.modules.obis.application.ports import CredentialsStore
from manashelper.modules.obis.errors import UserHasNoCredentialsError, UserNotFoundError


@dataclass(frozen=True, slots=True)
class IssueEdersLoginLinkUseCase:
    credentials_store: CredentialsStore
    tokens: EdersLoginTokens
    settings: Settings

    async def execute(self, user_id: int, locale: Locale) -> str:
        if not self.settings.eders_enabled or not self.settings.public_url:
            raise EdersFetchError("Browser login is disabled")
        credentials = await self.credentials_store.get_by_user_id(user_id)
        if credentials is None:
            raise UserNotFoundError(user_id)
        if not credentials.student_number:
            raise UserHasNoCredentialsError(user_id)
        token = self.tokens.issue(user_id, browser_login_marker(credentials))
        return f"{self.settings.public_url}/api/eders/browser-login?lang={locale.value}#{token}"
