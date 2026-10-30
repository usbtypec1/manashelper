import hashlib
from datetime import UTC, datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.eders.application.models import (
    ActivityKind,
    DeadlineFilter,
    EdersActivity,
    EdersSnapshot,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.errors import EdersLoginError
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.obis.application.credentials import ObisCredentialsService


def filter_activities(
    activities: tuple[EdersActivity, ...], selected: DeadlineFilter, now: datetime, hide_archived: bool = True
) -> list[EdersActivity]:
    results = []
    for activity in activities:
        if selected in {DeadlineFilter.MATERIALS, DeadlineFilter.NEW_MATERIALS}:
            if selected == DeadlineFilter.MATERIALS or activity.first_seen:
                results.append(activity)
            continue
        if activity.kind not in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
            continue
        closes = activity.closes.instant
        opens = activity.opens.instant
        if selected == DeadlineFilter.TODAY:
            include = closes is not None and closes.astimezone(BISHKEK_TZ).date() == now.astimezone(BISHKEK_TZ).date()
        elif selected == DeadlineFilter.NOT_SUBMITTED:
            include = activity.submission in {
                SubmissionStatus.NOT_SUBMITTED,
                SubmissionStatus.DRAFT,
                SubmissionStatus.IN_PROGRESS,
            }
        elif selected == DeadlineFilter.NEXT_SEVEN_DAYS:
            include = closes is not None and now <= closes <= now + timedelta(days=7)
        elif selected == DeadlineFilter.AVAILABLE:
            include = (
                opens is not None
                and opens <= now
                and closes is not None
                and now < closes
                and activity.submission != SubmissionStatus.SUBMITTED
            )
        elif selected == DeadlineFilter.AWAITING_GRADE:
            include = activity.submission == SubmissionStatus.SUBMITTED and activity.grading == GradingStatus.NOT_GRADED
        elif selected == DeadlineFilter.UNKNOWN_DEADLINE:
            include = closes is None
        else:
            # Hide dated activities from previous years. With an unknown timezone,
            # the bot cannot safely classify an item as archived.
            include = not hide_archived or closes is None or closes >= now - timedelta(days=180)
        if include:
            results.append(activity)
    if selected in {DeadlineFilter.MATERIALS, DeadlineFilter.NEW_MATERIALS}:
        return sorted(results, key=lambda item: (item.course.name, item.section, item.name))
    return sorted(results, key=lambda item: (item.closes.instant or datetime.max.replace(tzinfo=UTC), item.name))


class EdersService:
    def __init__(
        self,
        credentials: ObisCredentialsService,
        eders_client: EdersClient,
        eders_tracking_service: EdersTrackingService,
    ) -> None:
        self._credentials = credentials
        self._client = eders_client
        self._tracking = eders_tracking_service

    async def get_snapshot(self, user_id: int) -> EdersSnapshot:
        await self._tracking.get_settings(user_id)
        student_number = await self._credentials.get_student_number(user_id)
        marker = hashlib.sha256(student_number.encode()).hexdigest()
        return await self._tracking.get_snapshot(user_id, marker)

    async def refresh_snapshot(self, user_id: int) -> EdersSnapshot:
        await self._tracking.get_settings(user_id)
        await self._tracking.lock(user_id)
        student_number = await self._credentials.get_student_number(user_id)
        try:
            snapshot = await self._client.fetch_snapshot(student_number)
        except EdersLoginError:
            credentials = await self._credentials.get_credentials(user_id)
            snapshot = await self._client.fetch_snapshot(student_number, credentials.plain_password)
        marker = hashlib.sha256(student_number.encode()).hexdigest()
        return await self._tracking.observe(user_id, marker, snapshot)
