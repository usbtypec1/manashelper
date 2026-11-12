from dataclasses import dataclass

from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
from manashelper.modules.obis.application.credentials import ObisCredentialsQuery, get_results_credentials
from manashelper.modules.obis.application.ports import CredentialsStore, ResultsSource
from manashelper.modules.obis.application.sessions import ObisSessions


@dataclass(frozen=True, slots=True)
class RefreshObisTranscriptUseCase:
    credentials: ObisCredentialsQuery
    store: CredentialsStore
    source: ResultsSource
    sessions: ObisSessions
    record: RecordTranscriptUseCase
    gamification: GamificationQuery

    async def execute(self, user_id: int) -> None:
        if not await self.gamification.is_enabled(user_id):
            return
        await self.store.lock(user_id)
        credentials = await get_results_credentials(self.credentials, user_id)
        transcript = await self.source.fetch_transcript(await self.sessions.get_cookies(user_id))
        await self.record.execute(user_id, credentials.student_number, transcript)
