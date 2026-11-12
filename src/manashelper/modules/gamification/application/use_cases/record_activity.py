from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository


@dataclass(frozen=True, slots=True)
class RecordActivityUseCase:
    repository: AchievementRepository
    awards: AwardAchievementUseCase

    async def execute(
        self,
        user_id: int,
        activity: Literal["food", "grades", "published", "rating"],
        *,
        observed_at: datetime | None = None,
    ) -> None:
        now = observed_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("Activity time must be timezone-aware")
        progress = await self.repository.lock_progress(user_id)
        if progress is None:
            return
        if activity == "food":
            if progress.last_food_view is not None and now - progress.last_food_view < timedelta(minutes=10):
                return
            progress.food_views += 1
            progress.last_food_view = now
            if progress.food_views >= 50:
                await self.awards.execute(user_id, "foodie", now)
            if progress.food_views >= 100:
                await self.awards.execute(user_id, "cafeteria_boss", now)
        elif activity == "grades":
            local = now.astimezone(BISHKEK_TZ)
            if not 2 <= local.hour < 5:
                return
            today = local.date()
            if progress.last_night_date is not None and today <= progress.last_night_date:
                return
            progress.night_streak = (
                progress.night_streak + 1 if progress.last_night_date == today - timedelta(days=1) else 1
            )
            progress.last_night_date = today
            if progress.night_streak >= 3:
                await self.awards.execute(user_id, "night_owl", now)
        elif activity == "published":
            await self.awards.execute(user_id, "seller", now)
        elif activity == "rating":
            # Callers report only a user's first rating of a daily menu, not later score changes.
            progress.menu_ratings += 1
            if progress.menu_ratings >= 100:
                await self.awards.execute(user_id, "critic", now)
