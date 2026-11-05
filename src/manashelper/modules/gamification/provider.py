from dishka import Provider, Scope, provide

from manashelper.modules.gamification.application.queries import GamificationQuery
from manashelper.modules.gamification.application.use_cases.record_activity import RecordActivityUseCase
from manashelper.modules.gamification.application.use_cases.record_attendance import RecordAttendanceUseCase
from manashelper.modules.gamification.application.use_cases.record_transcript import RecordTranscriptUseCase
from manashelper.modules.gamification.application.use_cases.set_gamification_enabled import (
    SetGamificationEnabledUseCase,
)
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


class GamificationProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(AchievementRepository)
    activity = provide(RecordActivityUseCase)
    attendance = provide(RecordAttendanceUseCase)
    access = provide(SetGamificationEnabledUseCase)
    transcript = provide(RecordTranscriptUseCase)
    query = provide(GamificationQuery)
