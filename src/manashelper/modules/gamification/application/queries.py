from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.gamification.application.catalog import ACHIEVEMENTS
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


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
class LeaderboardEntry:
    user_id: int
    full_name: str
    score: int
    rank: int


@dataclass(frozen=True, slots=True)
class GamificationQuery:
    repository: AchievementRepository

    async def is_enabled(self, user_id: int) -> bool:
        return await self.repository.is_enabled(user_id)

    async def profile(self, user_id: int) -> AchievementProfile:
        food, streak, night_date = await self.repository.get_progress(user_id)
        today = datetime.now(UTC).astimezone(BISHKEK_TZ).date()
        if night_date is None or night_date < today - timedelta(days=1):
            streak = 0
        awards = await self.repository.get_awards(user_id)
        academic_ready, baseline, current_gpa, aa_count = await self.repository.academic_progress(user_id)
        attendance_ready, attendance_count = await self.repository.attendance_progress(user_id)
        ranking = await self.repository.ranking(user_id)
        cards = []
        for achievement in ACHIEVEMENTS:
            earned = awards.get(achievement.key)
            progress: int | float = food if achievement.key in {"foodie", "cafeteria_boss"} else streak
            if achievement.key not in {"foodie", "cafeteria_boss", "night_owl"}:
                progress = 0
            available = True
            blocked_reason = None
            if achievement.key in {"formula_one", "champion", "comeback", "fall", "eldin_balasy"}:
                available = academic_ready
                blocked_reason = None if available else "source"
            if achievement.key == "eldin_balasy":
                progress = aa_count
            if achievement.key == "thin_ice":
                progress = attendance_count
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
        return tuple(LeaderboardEntry(*row) for row in await self.repository.ranking())
