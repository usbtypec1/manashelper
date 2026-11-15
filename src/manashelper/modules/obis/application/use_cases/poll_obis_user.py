import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from manashelper.modules.obis.application.models import RefreshResult
from manashelper.modules.obis.application.ports import ObisNotificationSender
from manashelper.modules.obis.application.sessions import ObisSessions
from manashelper.modules.obis.application.use_cases.auto_login_obis import AutoLoginObisUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_transcript import RefreshObisTranscriptUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisParseError,
    ObisSessionExpiredError,
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
    sessions: ObisSessions
    auto_login: AutoLoginObisUseCase

    async def execute(
        self, user_id: int, check_exam_grades: bool, check_lesson_skips: bool, sender: ObisNotificationSender
    ) -> None:
        try:
            await self._refresh(user_id, check_exam_grades, check_lesson_skips, sender)
        except ObisSessionExpiredError:
            try:
                if await self.auto_login.execute(user_id) is None:
                    await self._refresh(user_id, check_exam_grades, check_lesson_skips, sender)
                    return
            except (
                UserNotFoundError,
                UserHasNoCredentialsError,
                ObisLoginError,
                ObisParseError,
                ObisSessionExpiredError,
            ):
                logger.warning("Automatic OBIS session recovery failed for user %s", user_id)
            # Transport errors propagate: preserve the saved session and let the next
            # scheduled poll recover, without blindly repeating an uncertain POST.
            age = await self.sessions.expire(user_id)
            # Request manual intervention once only when automatic recovery is unavailable.
            if age is not None:
                logger.info("OBIS session for user %s expired after %s", user_id, age)
                await sender.session_expired()

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
