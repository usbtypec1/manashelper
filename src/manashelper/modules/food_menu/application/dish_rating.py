from dataclasses import dataclass

from manashelper.modules.food_menu.application.daily_menu import DishModel, to_dish_model
from manashelper.modules.food_menu.infrastructure.repositories.dish_rating import DishRatingRepository


@dataclass(frozen=True, slots=True)
class DishRatingQuery:
    ratings: DishRatingRepository

    async def next_unrated(self, user_id: int) -> DishModel | None:
        dish = await self.ratings.next_unrated(user_id)
        return to_dish_model(dish) if dish is not None else None
