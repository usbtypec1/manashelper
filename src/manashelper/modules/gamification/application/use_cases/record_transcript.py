import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.obis.application.models import Transcript, TranscriptSemester

FAILING_GRADES = frozenset({"F1", "FF"})
PASSING_GRADES = frozenset({"AA", "BA", "BB", "CB", "CC", "DC", "DD"})
# Physics in Russian/Kyrgyz, Turkish (including "fiziği") and English, but not the
# "physical" adjective used by physical chemistry, geography or education.
PHYSICS = re.compile(r"(физик|fizi[kg]|physic)(?!sel|алык|al)")


def semester_gpa(term: TranscriptSemester) -> Decimal | None:
    if not term.credits or term.points is None:
        return None
    return (term.points / term.credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def is_physics(course_name: str) -> bool:
    # NFKD removes Turkish diacritics, including the dot that casefold leaves on "İ".
    text = unicodedata.normalize("NFKD", course_name.casefold())
    return PHYSICS.search("".join(char for char in text if not unicodedata.combining(char))) is not None


def has_stable_streak(semesters: tuple[TranscriptSemester, ...]) -> bool:
    # Regular semesters with official totals; summer school and unfinished terms neither count nor break it.
    streak = 0
    for term in semesters:
        gpa = semester_gpa(term) if term.key.endswith((":fall", ":spring")) else None
        if gpa is None:
            continue
        streak = streak + 1 if gpa >= Decimal("3.00") else 0
        if streak >= 3:
            return True
    return False


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
        same_account = progress.academic_marker == marker
        same_term = same_account and progress.academic_term == transcript.semesters[-1].key
        saved_baseline = progress.gpa_baseline if same_term else None
        progress.academic_marker = marker
        progress.academic_term = transcript.semesters[-1].key
        progress.gpa_current = transcript.overall_gpa
        progress.aa_count = max(sum(course.grade == "AA" for course in term.courses) for term in transcript.semesters)
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
        courses = [course for term in transcript.semesters for course in term.courses]
        grades = {course.grade for course in courses}
        if "F1" in grades:
            await self.awards.execute(user_id, "formula_one", now)
        if "FF" in grades:
            await self.awards.execute(user_id, "champion", now)
        if has_stable_streak(transcript.semesters):
            await self.awards.execute(user_id, "stability", now)
        if any(course.grade in FAILING_GRADES and is_physics(course.name) for course in courses):
            await self.awards.execute(user_id, "einstein", now)
        # Chronological attempts per course code. Earlier failures are remembered because
        # OBIS may replace a failed row with the retake result.
        attempts: dict[str, list[str]] = {}
        for course in courses:
            if course.code and course.grade:
                attempts.setdefault(course.code, []).append(course.grade)
        failed = set(progress.failed_courses if same_account else ())
        failed |= {code for code, results in attempts.items() if FAILING_GRADES.intersection(results)}
        progress.failed_courses = sorted(failed)
        if any(code in attempts and attempts[code][-1] in PASSING_GRADES for code in failed):
            await self.awards.execute(user_id, "phoenix", now)
