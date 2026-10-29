from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from manashelper.core.config import Settings
from manashelper.modules.eders.application.models import ActivityDate, ActivityKind, EdersActivity, EdersCourse
from manashelper.modules.eders.infrastructure.client import EdersClient

NOW = datetime(2026, 10, 1, tzinfo=UTC)


def make_eders_client(password="fake-password"):
    return EdersClient(Settings.model_construct(eders_password=SecretStr(password) if password is not None else None))


def item(**changes):
    return replace(
        EdersActivity(
            20,
            EdersCourse(10, "Course"),
            ActivityKind.ASSIGNMENT,
            "Work",
            "https://eders.manas.edu.kg/mod/assign/view.php?id=20",
            opens=ActivityDate(NOW + timedelta(days=1)),
            closes=ActivityDate(NOW + timedelta(days=3)),
        ),
        **changes,
    )
