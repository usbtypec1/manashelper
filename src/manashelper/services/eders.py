import hashlib
from datetime import UTC, datetime, timedelta

from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.eders_client import EdersClient
from manashelper.services.crypto import CryptoService, DecryptionError
from manashelper.services.eders_models import (
    ActivityKind,
    DeadlineFilter,
    EdersActivity,
    EdersSnapshot,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.obis import UserHasNoCredentialsError, UserNotFoundError


def filter_activities(
    activities: tuple[EdersActivity, ...], selected: DeadlineFilter, now: datetime, hide_archived: bool = True
) -> list[EdersActivity]:
    results = []
    for activity in activities:
        if activity.kind not in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
            continue
        closes = activity.closes.instant
        opens = activity.opens.instant
        if selected == DeadlineFilter.NEXT_SEVEN_DAYS:
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
    return sorted(results, key=lambda item: (item.closes.instant or datetime.max.replace(tzinfo=UTC), item.name))


class EdersService:
    def __init__(
        self,
        user_repository: UserRepository,
        eders_client: EdersClient,
        crypto_service: CryptoService,
        eders_tracking_service: EdersTrackingService,
    ) -> None:
        self._users = user_repository
        self._client = eders_client
        self._crypto = crypto_service
        self._tracking = eders_tracking_service

    async def get_snapshot(self, user_id: int) -> EdersSnapshot:
        await self._tracking.get_settings(user_id)
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if user.student_number is None or user.encrypted_password is None:
            raise UserHasNoCredentialsError(user_id)
        try:
            password = self._crypto.decrypt(user.encrypted_password)
        except DecryptionError:
            raise UserHasNoCredentialsError(user_id) from None
        snapshot = await self._client.fetch_snapshot(user.student_number, password)
        marker = hashlib.sha256(user.encrypted_password.encode()).hexdigest()
        return await self._tracking.observe(user_id, marker, snapshot)
