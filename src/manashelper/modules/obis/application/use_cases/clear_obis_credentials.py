from dataclasses import dataclass

from manashelper.modules.obis.application.credentials import ObisCredentialsQuery
from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.application.ports import CredentialsStore, SnapshotStore


@dataclass(frozen=True, slots=True)
class ClearObisCredentialsUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    snapshots: SnapshotStore

    async def execute(self, user_id: int) -> None:
        await self.store.lock(user_id)
        await self.credentials.get_stored_credentials(user_id)
        await self.store.save(user_id, StoredCredentials(None, None))
        await self.snapshots.reset(user_id)
