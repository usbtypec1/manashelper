from dishka import Provider, Scope, provide

from manashelper.modules.food_menu.application.daily_menu import DailyMenuQuery
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuSettingsQuery,
)
from manashelper.modules.food_menu.application.use_cases.broadcast_food_menu import BroadcastFoodMenuUseCase
from manashelper.modules.food_menu.application.use_cases.disable_food_menu_notifications import (
    DisableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.enable_food_menu_notifications import (
    EnableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.get_daily_menu import GetDailyMenuUseCase
from manashelper.modules.food_menu.application.use_cases.get_daily_menu_by_offset import GetDailyMenuByOffsetUseCase
from manashelper.modules.food_menu.application.use_cases.rate_daily_menu import RateDailyMenuUseCase
from manashelper.modules.food_menu.application.use_cases.sync_food_menus import SyncFoodMenusUseCase
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal import ToggleFoodMenuMealUseCase
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal_for_week import (
    ToggleFoodMenuMealForWeekUseCase,
)
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_weekday import ToggleFoodMenuWeekdayUseCase
from manashelper.modules.food_menu.infrastructure.food_menu_client import FoodMenuClient
from manashelper.modules.food_menu.infrastructure.food_menu_parser import FoodMenuParser
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu import DailyMenuRepository
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu_rating import (
    DailyMenuRatingRepository,
)
from manashelper.modules.food_menu.infrastructure.repositories.dish import DishRepository
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings import (
    FoodMenuNotificationSettingsRepository,
)


class FoodMenuProvider(Provider):
    scope = Scope.REQUEST

    disable_food_menu_notifications_use_case = provide(DisableFoodMenuNotificationsUseCase)

    enable_food_menu_notifications_use_case = provide(EnableFoodMenuNotificationsUseCase)

    toggle_food_menu_meal_for_week_use_case = provide(ToggleFoodMenuMealForWeekUseCase)

    toggle_food_menu_weekday_use_case = provide(ToggleFoodMenuWeekdayUseCase)

    toggle_food_menu_meal_use_case = provide(ToggleFoodMenuMealUseCase)

    rate_daily_menu_use_case = provide(RateDailyMenuUseCase)

    get_daily_menu_by_offset_use_case = provide(GetDailyMenuByOffsetUseCase)

    get_daily_menu_use_case = provide(GetDailyMenuUseCase)

    client = provide(FoodMenuClient, scope=Scope.APP)
    parser = provide(FoodMenuParser, scope=Scope.APP)
    menus = provide(DailyMenuRepository)
    ratings = provide(DailyMenuRatingRepository)
    dishes = provide(DishRepository)
    notification_settings = provide(FoodMenuNotificationSettingsRepository)
    daily_menu = provide(DailyMenuQuery)
    sync = provide(SyncFoodMenusUseCase)
    notifications = provide(FoodMenuSettingsQuery)
    broadcast = provide(BroadcastFoodMenuUseCase)
