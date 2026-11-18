from dataclasses import dataclass

from manashelper.modules.eders.application.browser_login import EdersLoginTokens, browser_login_marker
from manashelper.modules.eders.errors import InvalidEdersLoginLinkError
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.ports import CredentialsStore


@dataclass(frozen=True, slots=True)
class RedeemEdersLoginLinkUseCase:
    credentials_store: CredentialsStore
    tokens: EdersLoginTokens
    eders_client: EdersClient
    obis_access: ObisAccessService

    async def execute(self, token: str) -> str:
        grant = self.tokens.consume(token)
        await self.credentials_store.lock(grant.user_id)
        credentials = await self.credentials_store.get_by_user_id(grant.user_id)
        if (
            credentials is None
            or not credentials.student_number
            or browser_login_marker(credentials) != grant.credential_marker
        ):
            raise InvalidEdersLoginLinkError
        return await self.obis_access.with_session(grant.user_id, self.eders_client.create_browser_login_url)
