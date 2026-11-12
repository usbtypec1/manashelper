import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.models import LessonAttendanceModel

# From November 1 and April 1 until the semester ends: an early-semester snapshot is trivially clean.
IRON_ATTENDANCE_MONTHS = frozenset({11, 12, 1, 4, 5, 6})


def has_perfect_attendance(lessons: list[LessonAttendanceModel]) -> bool:
    percentages = [
        value
        for lesson in lessons
        for value in (lesson.theory_skips_percentage, lesson.practice_skips_percentage)
        if value is not None
    ]
    return bool(percentages) and all(value == 0 for value in percentages)


@dataclass(frozen=True, slots=True)
class RecordAttendanceUseCase:
    repository: AchievementRepository
    awards: AwardAchievementUseCase

    async def execute(
        self,
        user_id: int,
        student_number: str,
        lessons: list[LessonAttendanceModel],
        *,
        observed_at: datetime | None = None,
    ) -> None:
        now = observed_at or datetime.now(UTC)
        progress = await self.repository.lock_progress(user_id)
        if progress is None:
            return
        # One current-semester snapshot; theory and practice never count as two subjects.
        qualifying = {
            lesson.lesson_code
            for lesson in lessons
            if lesson.lesson_code
            and any(
                value is not None and 18.75 <= value <= 100
                for value in (lesson.theory_skips_percentage, lesson.practice_skips_percentage)
            )
        }
        progress.attendance_marker = hashlib.sha256(student_number.encode()).hexdigest()
        progress.attendance_count = len(qualifying)
        if len(qualifying) >= 5:
            await self.awards.execute(user_id, "thin_ice", now)
        if now.astimezone(BISHKEK_TZ).month in IRON_ATTENDANCE_MONTHS and has_perfect_attendance(lessons):
            await self.awards.execute(user_id, "iron_attendance", now)
