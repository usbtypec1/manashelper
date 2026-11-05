import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.models import LessonAttendanceModel


@dataclass(frozen=True, slots=True)
class RecordAttendanceUseCase:
    repository: AchievementRepository

    async def execute(self, user_id: int, student_number: str, lessons: list[LessonAttendanceModel]) -> None:
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
            await self.repository.award(user_id, "thin_ice", datetime.now(UTC))
