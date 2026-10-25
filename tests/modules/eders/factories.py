from dataclasses import replace
from datetime import UTC, datetime, timedelta

from manashelper.modules.eders.application.models import ActivityDate, ActivityKind, EdersActivity, EdersCourse

NOW = datetime(2026, 10, 1, tzinfo=UTC)


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
