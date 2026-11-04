from types import SimpleNamespace

from manashelper.modules.eders.application.eders import EdersQuery
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.application.use_cases.refresh_eders_snapshot import RefreshEdersSnapshotUseCase
from manashelper.modules.eders.application.use_cases.toggle_eders_setting import ToggleEdersSettingUseCase


def build_eders_service(credentials, eders_client, eders_tracking_service):
    query = EdersQuery(credentials, eders_tracking_service)
    return SimpleNamespace(
        get_snapshot=query.get_snapshot,
        refresh_snapshot=RefreshEdersSnapshotUseCase(
            credentials=credentials, eders_client=eders_client, eders_tracking_service=eders_tracking_service
        ).execute,
    )


def build_eders_tracking_service(eders_repository, users, outbox):
    query = EdersTrackingService(eders_repository, users, outbox)
    return SimpleNamespace(
        get_settings=query.get_settings,
        get_snapshot=query.get_snapshot,
        lock=query.lock,
        observe=query.observe,
        pending_events=query.pending_events,
        mark_sent=query.mark_sent,
        get_poll_user_ids=query.get_poll_user_ids,
        toggle=ToggleEdersSettingUseCase(eders_repository=eders_repository, users=users, outbox=outbox).execute,
    )
