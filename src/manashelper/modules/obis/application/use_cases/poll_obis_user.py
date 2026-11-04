from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from manashelper.modules.obis.application.models import RefreshResult
from manashelper.modules.obis.application.ports import ObisNotificationSender
from manashelper.modules.obis.application.use_cases.refresh_obis_attendance import RefreshObisAttendanceUseCase
from manashelper.modules.obis.application.use_cases.refresh_obis_grades import RefreshObisGradesUseCase
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisParseError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)


async def _changes[T, C](check: Callable[[int], Awaitable[RefreshResult[T, C]]], user_id: int) -> list[C]:
    try:
        return (await check(user_id)).changes
    except (UserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError):
        return []


@dataclass(frozen=True, slots=True)
class PollObisUserUseCase:
    refresh_obis_grades: RefreshObisGradesUseCase
    refresh_obis_attendance: RefreshObisAttendanceUseCase

    async def execute(
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
