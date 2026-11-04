from types import SimpleNamespace

from manashelper.modules.food_menu.application.daily_menu import DailyMenuQuery
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuSettingsQuery,
)
from manashelper.modules.food_menu.application.use_cases.disable_food_menu_notifications import (
    DisableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.enable_food_menu_notifications import (
    EnableFoodMenuNotificationsUseCase,
)
from manashelper.modules.food_menu.application.use_cases.get_daily_menu import GetDailyMenuUseCase
from manashelper.modules.food_menu.application.use_cases.get_daily_menu_by_offset import GetDailyMenuByOffsetUseCase
from manashelper.modules.food_menu.application.use_cases.rate_daily_menu import RateDailyMenuUseCase
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal import ToggleFoodMenuMealUseCase
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_meal_for_week import (
    ToggleFoodMenuMealForWeekUseCase,
)
from manashelper.modules.food_menu.application.use_cases.toggle_food_menu_weekday import ToggleFoodMenuWeekdayUseCase


def build_daily_menu_service(daily_menu_repository, daily_menu_rating_repository):
    query = DailyMenuQuery(daily_menu_repository)
    return SimpleNamespace(
        get_available_dates=query.get_available_dates,
        get_daily_menu_by_date=GetDailyMenuUseCase(
            daily_menu_repository=daily_menu_repository, daily_menu_rating_repository=daily_menu_rating_repository
        ).execute,
        get_daily_menu_by_skipping_days=GetDailyMenuByOffsetUseCase(
            get_daily_menu=GetDailyMenuUseCase(
                daily_menu_repository=daily_menu_repository, daily_menu_rating_repository=daily_menu_rating_repository
            )
        ).execute,
        set_rating=RateDailyMenuUseCase(
            daily_menu_repository=daily_menu_repository, daily_menu_rating_repository=daily_menu_rating_repository
        ).execute,
    )


def build_food_menu_notification_settings_service(food_menu_notification_settings_repository, users):
    query = FoodMenuSettingsQuery(food_menu_notification_settings_repository, users)
    return SimpleNamespace(
        get_settings=query.get_settings,
        toggle=ToggleFoodMenuMealUseCase(
            food_menu_notification_settings_repository=food_menu_notification_settings_repository, users=users
        ).execute,
        toggle_weekday=ToggleFoodMenuWeekdayUseCase(
            food_menu_notification_settings_repository=food_menu_notification_settings_repository, users=users
        ).execute,
        toggle_meal=ToggleFoodMenuMealForWeekUseCase(
            food_menu_notification_settings_repository=food_menu_notification_settings_repository, users=users
        ).execute,
        enable_all=EnableFoodMenuNotificationsUseCase(
            food_menu_notification_settings_repository=food_menu_notification_settings_repository, users=users
        ).execute,
        disable_all=DisableFoodMenuNotificationsUseCase(
            food_menu_notification_settings_repository=food_menu_notification_settings_repository, users=users
        ).execute,
    )
