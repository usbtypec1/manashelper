import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from manashelper.modules.obis.application.access import ObisAccessService
from manashelper.modules.obis.application.models import RefreshResult
from manashelper.modules.obis.application.ports import ObisNotificationSender
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisManualLoginRequiredError,
    ObisParseError,
    ObisRetryLaterError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)


async def _changes[T, C](check: Callable[[int], Awaitable[RefreshResult[T, C]]], user_id: int) -> list[C]:
    try:
        return (await check(user_id)).changes
    except (UserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError):
        return []


@dataclass(frozen=True, slots=True)
class PollObisUserUseCase:
    refresh_obis_grades: RefreshObisGradesUseCase
    refresh_obis_attendance: RefreshObisAttendanceUseCase
    refresh_obis_transcript: RefreshObisTranscriptUseCase
    access: ObisAccessService

    async def execute(
        self, user_id: int, check_exam_grades: bool, check_lesson_skips: bool, sender: ObisNotificationSender
    ) -> None:
        try:
            await self._refresh(user_id, check_exam_grades, check_lesson_skips, sender)
        except ObisManualLoginRequiredError:
            if await self.access.claim_manual_login_notice(user_id):
                await sender.session_expired()
        except ObisRetryLaterError:
            # Catch inside the request scope so durable retry state commits.
            logger.info("OBIS polling postponed for user %s", user_id)
        else:
            await self.access.record_refresh_success(user_id)

    async def _refresh(
        self, user_id: int, check_exam_grades: bool, check_lesson_skips: bool, sender: ObisNotificationSender
    ) -> None:
        grade_changes = await _changes(self.refresh_obis_grades.execute, user_id)
        if check_exam_grades:
            for grade_change in grade_changes:
                await sender.exam_grade_changed(grade_change)
        skip_changes = await _changes(self.refresh_obis_attendance.execute, user_id)
        if check_lesson_skips:
            for skip_change in skip_changes:
                await sender.lesson_skips_changed(skip_change)
        try:
            await self.refresh_obis_transcript.execute(user_id)
        except (UserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError, httpx.HTTPError):
            logger.warning("Failed to refresh OBIS transcript for user %s", user_id, exc_info=True)
