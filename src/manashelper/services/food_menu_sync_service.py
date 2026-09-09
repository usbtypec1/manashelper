import re
import uuid

from manashelper.db.models import DailyMenu, Dish
from manashelper.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.repositories.dish_repository import DishRepository
from manashelper.scraping.food_menu_client import FoodMenuClient
from manashelper.scraping.food_menu_parser import FoodMenuParser, ScrapedDailyMenu

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_dish_name(name: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", name).strip().lower()


class FoodMenuSyncService:
    def __init__(
        self,
        food_menu_client: FoodMenuClient,
        food_menu_parser: FoodMenuParser,
        daily_menu_repository: DailyMenuRepository,
        dish_repository: DishRepository,
    ) -> None:
        self._food_menu_client = food_menu_client
        self._food_menu_parser = food_menu_parser
        self._daily_menu_repository = daily_menu_repository
        self._dish_repository = dish_repository

    async def synchronize_daily_menus(self) -> None:
        html = await self._food_menu_client.fetch_menu_html()
        scraped_daily_menus = self._food_menu_parser.parse(html)
        for scraped_daily_menu in scraped_daily_menus:
            await self._synchronize_daily_menu(scraped_daily_menu)

    async def _synchronize_daily_menu(self, scraped_daily_menu: ScrapedDailyMenu) -> None:
        daily_menu = await self._daily_menu_repository.get_by_date(scraped_daily_menu.date)

        existing_names = {_normalize_dish_name(dish.name) for dish in daily_menu.dishes} if daily_menu else set()
        scraped_names = {_normalize_dish_name(dish.name) for dish in scraped_daily_menu.dishes}
        if daily_menu is not None and existing_names == scraped_names:
            return

        dishes = []
        for scraped_dish in scraped_daily_menu.dishes:
            dish = await self._dish_repository.get_by_name(scraped_dish.name)
            if dish is None:
                dish = Dish(
                    id=uuid.uuid4(),
                    name=scraped_dish.name,
                    photo_url=scraped_dish.photo_url,
                    calories=scraped_dish.calories,
                )
                self._dish_repository.add(dish)
            dishes.append(dish)

        # A brand-new DailyMenu must get its `dishes` populated at construction time, not via a
        # later attribute assignment: the dish lookups above can autoflush this pending row to the
        # database, and assigning to a relationship collection that SQLAlchemy now considers
        # persisted-but-unloaded triggers a synchronous lazy-load of the old value for change
        # tracking, which fails under the async engine (MissingGreenlet).
        if daily_menu is None:
            daily_menu = DailyMenu(id=uuid.uuid4(), date=scraped_daily_menu.date, views_count=0, dishes=dishes)
            self._daily_menu_repository.add(daily_menu)
        else:
            daily_menu.dishes = dishes
