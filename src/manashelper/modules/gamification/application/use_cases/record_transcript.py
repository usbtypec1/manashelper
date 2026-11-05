import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.models import Transcript


@dataclass(frozen=True, slots=True)
class RecordTranscriptUseCase:
    repository: AchievementRepository
    awards: AwardAchievementUseCase

    async def execute(self, user_id: int, student_number: str, transcript: Transcript) -> None:
        progress = await self.repository.lock_progress(user_id)
        if progress is None:
            return
        now = datetime.now(UTC)
        marker = hashlib.sha256(student_number.encode()).hexdigest()
        same_term = progress.academic_marker == marker and progress.academic_term == transcript.semesters[-1].key
        saved_baseline = progress.gpa_baseline if same_term else None
        progress.academic_marker = marker
        progress.academic_term = transcript.semesters[-1].key
        progress.gpa_current = transcript.overall_gpa
        progress.aa_count = max(term.grades.count("AA") for term in transcript.semesters)
        if progress.aa_count >= 3:
            await self.awards.execute(user_id, "eldin_balasy", now)
        # Reconstruct the cumulative GPA before the latest semester from OBIS's
        # official credit/point totals. An unfinished semester has no GPA yet.
        previous = transcript.semesters[:-1]
        complete = all(term.credits is not None and term.points is not None for term in previous)
        credits = sum((term.credits or Decimal(0) for term in previous), Decimal(0))
        points = sum((term.points or Decimal(0) for term in previous), Decimal(0))
        baseline = (
            (points / credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if complete and credits else None
        )
        baseline = saved_baseline if saved_baseline is not None else baseline
        progress.gpa_baseline = baseline
        if baseline is not None:
            delta = transcript.overall_gpa - baseline
            if delta >= Decimal("0.20"):
                await self.awards.execute(user_id, "comeback", now)
            if delta <= Decimal("-0.20"):
                await self.awards.execute(user_id, "fall", now)
        grades = {grade for term in transcript.semesters for grade in term.grades}
        if "F1" in grades:
            await self.awards.execute(user_id, "formula_one", now)
        if "FF" in grades:
            await self.awards.execute(user_id, "champion", now)
