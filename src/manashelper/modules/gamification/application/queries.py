from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.gamification.application.catalog import ACHIEVEMENTS
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository

ACADEMIC_KEYS = frozenset(
    {"formula_one", "champion", "comeback", "fall", "eldin_balasy", "phoenix", "stability", "einstein"}
)
ATTENDANCE_KEYS = frozenset({"thin_ice", "iron_attendance"})


@dataclass(frozen=True, slots=True)
class AchievementCard:
    key: str
    emoji: str
    current: int | float
    target: int | float
    earned_at: str | None
    available: bool
    blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class AchievementProfile:
    score: int
    total: int
    rank: int | None
    achievements: tuple[AchievementCard, ...]


@dataclass(frozen=True, slots=True)
class EarnedAchievement:
    key: str
    earned_at: str


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    user_id: int
    full_name: str
    score: int
    rank: int
    achievements: tuple[EarnedAchievement, ...]


@dataclass(frozen=True, slots=True)
class GamificationQuery:
    repository: AchievementRepository

    async def is_enabled(self, user_id: int) -> bool:
        return await self.repository.is_enabled(user_id)

    async def profile(self, user_id: int) -> AchievementProfile:
        food, streak, night_date, ratings = await self.repository.get_progress(user_id)
        today = datetime.now(UTC).astimezone(BISHKEK_TZ).date()
        if night_date is None or night_date < today - timedelta(days=1):
            streak = 0
        awards = await self.repository.get_awards(user_id)
        academic_ready, baseline, current_gpa, aa_count = await self.repository.academic_progress(user_id)
        attendance_ready, attendance_count = await self.repository.attendance_progress(user_id)
        ranking = await self.repository.ranking(user_id)
        counters: dict[str, int] = {
            "foodie": food,
            "cafeteria_boss": food,
            "night_owl": streak,
            "critic": ratings,
            "eldin_balasy": aa_count,
            "thin_ice": attendance_count,
        }
        cards = []
        for achievement in ACHIEVEMENTS:
            earned = awards.get(achievement.key)
            progress: int | float = counters.get(achievement.key, 0)
            available = True
            blocked_reason = None
            if achievement.key in ACADEMIC_KEYS:
                available = academic_ready
                blocked_reason = None if available else "source"
            if achievement.key in ATTENDANCE_KEYS:
                available = attendance_ready
                blocked_reason = None if available else "source"
            if achievement.key in {"comeback", "fall"}:
                if academic_ready and baseline is None:
                    available = False
                    blocked_reason = "baseline"
                if baseline is not None and current_gpa is not None:
                    delta = float(current_gpa - baseline)
                    progress = round(max(0, delta if achievement.key == "comeback" else -delta), 2)
            cards.append(
                AchievementCard(
                    achievement.key,
                    achievement.emoji,
                    achievement.target if earned else min(progress, achievement.target),
                    achievement.target,
                    earned.isoformat() if earned else None,
                    available,
                    blocked_reason,
                )
            )
        return AchievementProfile(len(awards), len(ACHIEVEMENTS), ranking[0][3] if ranking else None, tuple(cards))

    async def leaderboard(self) -> tuple[LeaderboardEntry, ...]:
        ranking = await self.repository.ranking()
        awards = await self.repository.get_awards_for_users([row[0] for row in ranking])
        return tuple(
            LeaderboardEntry(
                user_id,
                name,
                score,
                rank,
                tuple(
                    EarnedAchievement(achievement.key, earned_at.isoformat())
                    for achievement in ACHIEVEMENTS
                    if (earned_at := awards.get(user_id, {}).get(achievement.key)) is not None
                ),
            )
            for user_id, name, score, rank in ranking
        )
