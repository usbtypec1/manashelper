import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    EdersActivity,
    EdersCourse,
    EdersSnapshot,
    GradingStatus,
    SubmissionStatus,
)


def serialize_snapshot(snapshot: EdersSnapshot) -> str:
    def encode(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError("Unsupported snapshot value")

    return json.dumps(asdict(snapshot), default=encode, ensure_ascii=False)


def deserialize_snapshot(payload: str) -> EdersSnapshot:
    data = json.loads(payload)

    def date(value: dict[str, Any]) -> ActivityDate:
        return ActivityDate(
            datetime.fromisoformat(value["instant"]) if value["instant"] else None,
            value["source_text"],
            value["conflict"],
        )

    activities = tuple(
        EdersActivity(
            id=value["id"],
            course=EdersCourse(**value["course"]),
            kind=ActivityKind(value["kind"]),
            name=value["name"],
            url=value["url"],
            opens=date(value["opens"]),
            closes=date(value["closes"]),
            submission=SubmissionStatus(value["submission"]),
            grading=GradingStatus(value["grading"]),
            title_date_mismatch=value["title_date_mismatch"],
            first_seen=datetime.fromisoformat(value["first_seen"]) if value["first_seen"] else None,
        )
        for value in data["activities"]
    )
    return EdersSnapshot(activities, datetime.fromisoformat(data["fetched_at"]))
