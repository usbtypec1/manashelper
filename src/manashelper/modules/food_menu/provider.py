from dishka import Provider, Scope, provide

from manashelper.modules.food_menu.application.broadcast import BroadcastFoodMenu
from manashelper.modules.food_menu.application.daily_menu import DailyMenuService
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuNotificationSettingsService,
)
from manashelper.modules.food_menu.application.food_menu_sync import FoodMenuSyncService
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

    client = provide(FoodMenuClient, scope=Scope.APP)
    parser = provide(FoodMenuParser, scope=Scope.APP)
    menus = provide(DailyMenuRepository)
    ratings = provide(DailyMenuRatingRepository)
    dishes = provide(DishRepository)
    notification_settings = provide(FoodMenuNotificationSettingsRepository)
    daily_menu = provide(DailyMenuService)
    sync = provide(FoodMenuSyncService)
    notifications = provide(FoodMenuNotificationSettingsService)
    broadcast = provide(BroadcastFoodMenu)
