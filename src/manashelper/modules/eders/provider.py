from dishka import Provider, Scope, provide

from manashelper.modules.eders.application.eders import EdersQuery
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.poll_eders_user import PollEdersUserUseCase
from manashelper.modules.eders.application.use_cases.refresh_eders_snapshot import RefreshEdersSnapshotUseCase
from manashelper.modules.eders.application.use_cases.set_activity_completion import SetActivityCompletionUseCase
from manashelper.modules.eders.application.use_cases.toggle_eders_setting import ToggleEdersSettingUseCase
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository


class EdersProvider(Provider):
    scope = Scope.REQUEST

    toggle_eders_setting_use_case = provide(ToggleEdersSettingUseCase)

    refresh_eders_snapshot_use_case = provide(RefreshEdersSnapshotUseCase)
    set_activity_completion_use_case = provide(SetActivityCompletionUseCase)
    client = provide(EdersClient, scope=Scope.APP)
    repository = provide(EdersRepository, scope=Scope.REQUEST)
    eders_query = provide(EdersQuery, scope=Scope.REQUEST)
    tracking = provide(EdersTrackingService, scope=Scope.REQUEST)
    polling = provide(PollEdersUserUseCase, scope=Scope.REQUEST)
