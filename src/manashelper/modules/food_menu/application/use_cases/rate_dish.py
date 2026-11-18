import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from manashelper.modules.food_menu.application.daily_menu import DishModel
from manashelper.modules.food_menu.application.dish_rating import DishRatingQuery
from manashelper.modules.food_menu.infrastructure.repositories.dish_rating import DishRatingRepository
from manashelper.modules.gamification.application.catalog import ACHIEVEMENT_KEYS, DISH_COMPLETION_ACHIEVEMENT
from manashelper.modules.gamification.application.use_cases.award_achievement import AwardAchievementUseCase


@dataclass(frozen=True, slots=True)
class RateDishUseCase:
    ratings: DishRatingRepository
    query: DishRatingQuery
    awards: AwardAchievementUseCase

    async def execute(self, user_id: int, dish_id: uuid.UUID, score: int) -> DishModel | None:
        if not 1 <= score <= 5:
            raise ValueError("Dish rating must be between 1 and 5")
        saved = await self.ratings.add_score(dish_id, user_id, score)
        next_dish = await self.query.next_unrated(user_id)
        key = DISH_COMPLETION_ACHIEVEMENT.key
        if saved and next_dish is None and key in ACHIEVEMENT_KEYS:
            await self.awards.execute(user_id, key, datetime.now(UTC))
        return next_dish
