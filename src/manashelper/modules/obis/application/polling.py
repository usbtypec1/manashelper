from collections.abc import Awaitable, Callable
from typing import Protocol

from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange, ObisNotificationService
from manashelper.modules.obis.errors import (
    ObisLoginError,
    ObisParseError,
    UserHasNoCredentialsError,
    UserNotFoundError,
)


class ObisNotificationSender(Protocol):
    async def exam_grade_changed(self, change: ExamGradeChange) -> None: ...

    async def lesson_skips_changed(self, change: LessonSkipChange) -> None: ...


async def _changes[T](check: Callable[[int], Awaitable[list[T]]], user_id: int) -> list[T]:
    try:
        return await check(user_id)
    except (UserNotFoundError, UserHasNoCredentialsError, ObisLoginError, ObisParseError):
        return []


class PollObisUser:
    def __init__(self, notifications: ObisNotificationService) -> None:
        self._notifications = notifications

    async def execute(
        self, user_id: int, check_exam_grades: bool, check_lesson_skips: bool, sender: ObisNotificationSender
    ) -> None:
        grade_changes = await _changes(self._notifications.check_exam_grade_changes, user_id)
        if check_exam_grades:
            for grade_change in grade_changes:
                await sender.exam_grade_changed(grade_change)
        skip_changes = await _changes(self._notifications.check_lesson_skip_changes, user_id)
        if check_lesson_skips:
            for skip_change in skip_changes:
                await sender.lesson_skips_changed(skip_change)
