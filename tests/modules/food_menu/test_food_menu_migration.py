import uuid
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Message
from dishka import make_async_container

from manashelper.core.provider import CoreProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.food_menu import jobs
from manashelper.modules.food_menu.application import broadcast as broadcast_module
from manashelper.modules.food_menu.application.broadcast import BroadcastFoodMenu
from manashelper.modules.food_menu.application.daily_menu import (
    DailyMenuModel,
    DailyMenuNotFoundError,
)
from manashelper.modules.food_menu.application.food_menu_cleanup_settings import FoodMenuCleanupSettingsService
from manashelper.modules.food_menu.application.food_menu_notification_settings import (
    FoodMenuMeal,
    FoodMenuNotificationSettingsService,
    UserNotFoundError,
)
from manashelper.modules.food_menu.application.food_menu_sync import FoodMenuSyncService
from manashelper.modules.food_menu.infrastructure.food_menu_client import FoodMenuClient
from manashelper.modules.food_menu.infrastructure.food_menu_parser import FoodMenuParser, ScrapedDailyMenu, ScrapedDish
from manashelper.modules.food_menu.infrastructure.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.modules.food_menu.infrastructure.repositories.dish_repository import DishRepository
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.modules.food_menu.presentation.callbacks import FoodMenuNotificationDayCallback
from manashelper.modules.food_menu.presentation.routers.food_menu_notifications import (
    on_open_food_menu_notifications,
    on_toggle_food_menu_notification_day,
)
from manashelper.modules.food_menu.presentation.sender import TelegramFoodMenuSender
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.provider import UsersProvider
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.provider import TelegramPlatformProvider


async def test_notification_defaults_weekday_meal_and_bulk_toggles(session):
    session.add(User(id=960001, full_name="Menu settings"))
    await session.flush()
    repository = FoodMenuNotificationSettingsRepository(session)
    service = FoodMenuNotificationSettingsService(repository, UsersQuery(UserRepository(session)))
    summary = await service.get_settings(960001)
    assert [(day.weekday, day.lunch_enabled, day.dinner_enabled) for day in summary.days] == [
        (weekday, True, True) for weekday in range(7)
    ]
    summary = await service.toggle(960001, 2, FoodMenuMeal.LUNCH)
    assert (summary.days[2].lunch_enabled, summary.days[2].dinner_enabled) == (False, True)
    summary = await service.toggle(960001, 2, FoodMenuMeal.LUNCH)
    assert (summary.days[2].lunch_enabled, summary.days[2].dinner_enabled) == (True, True)
    summary = await service.toggle_weekday(960001, 2)
    assert (summary.days[2].lunch_enabled, summary.days[2].dinner_enabled) == (False, False)
    summary = await service.toggle_weekday(960001, 2)
    assert (summary.days[2].lunch_enabled, summary.days[2].dinner_enabled) == (True, True)
    summary = await service.toggle_meal(960001, FoodMenuMeal.DINNER)
    assert all(day.lunch_enabled and not day.dinner_enabled for day in summary.days)
    summary = await service.toggle_meal(960001, FoodMenuMeal.DINNER)
    assert all(day.lunch_enabled and day.dinner_enabled for day in summary.days)
    summary = await service.disable_all(960001)
    assert all(not day.lunch_enabled and not day.dinner_enabled for day in summary.days)
    summary = await service.enable_all(960001)
    assert all(day.lunch_enabled and day.dinner_enabled for day in summary.days)
    assert await repository.get_all_by_user_id(960001) == []


@pytest.mark.parametrize(
    "action,args,disabled",
    [
        ("toggle", (2, FoodMenuMeal.LUNCH), {(2, FoodMenuMeal.LUNCH)}),
        ("toggle", (2, FoodMenuMeal.DINNER), {(2, FoodMenuMeal.DINNER)}),
        ("toggle_weekday", (2,), {(2, FoodMenuMeal.LUNCH), (2, FoodMenuMeal.DINNER)}),
        ("toggle_meal", (FoodMenuMeal.LUNCH,), {(day, FoodMenuMeal.LUNCH) for day in range(7)}),
        ("toggle_meal", (FoodMenuMeal.DINNER,), {(day, FoodMenuMeal.DINNER) for day in range(7)}),
    ],
)
async def test_first_food_toggle_disables_selection_and_survives_reload(session, action, args, disabled):
    session.add(User(id=960001, full_name="Menu settings"))
    await session.flush()
    service = FoodMenuNotificationSettingsService(
        FoodMenuNotificationSettingsRepository(session), UsersQuery(UserRepository(session))
    )
    summary = await getattr(service, action)(960001, *args)
    for day in summary.days:
        assert day.lunch_enabled is ((day.weekday, FoodMenuMeal.LUNCH) not in disabled)
        assert day.dinner_enabled is ((day.weekday, FoodMenuMeal.DINNER) not in disabled)
    await session.commit()
    session.expire_all()
    assert await service.get_settings(960001) == summary
    repeated = await getattr(service, action)(960001, *args)
    assert all(day.lunch_enabled and day.dinner_enabled for day in repeated.days)


async def test_new_weekday_toggle_preserves_other_saved_preferences(session):
    session.add(User(id=960001, full_name="Menu settings"))
    await session.flush()
    repository = FoodMenuNotificationSettingsRepository(session)
    row = await repository.get_or_create(960001, 1)
    row.lunch_enabled = row.dinner_enabled = False
    await session.commit()
    session.expire_all()
    service = FoodMenuNotificationSettingsService(repository, UsersQuery(UserRepository(session)))
    summary = await service.toggle(960001, 2, FoodMenuMeal.LUNCH)
    assert (summary.days[1].lunch_enabled, summary.days[1].dinner_enabled) == (False, False)
    assert (summary.days[2].lunch_enabled, summary.days[2].dinner_enabled) == (False, True)
    assert all(day.lunch_enabled and day.dinner_enabled for day in summary.days if day.weekday not in {1, 2})


@pytest.mark.parametrize("meal", list(FoodMenuMeal))
async def test_first_food_click_updates_visible_button_and_persisted_preference(session, meal):
    session.add(User(id=960001, full_name="Menu settings"))
    await session.flush()
    service = FoodMenuNotificationSettingsService(
        FoodMenuNotificationSettingsRepository(session), UsersQuery(UserRepository(session))
    )
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = SimpleNamespace(id=960001)
    callback.message = AsyncMock(spec=Message)
    callback.message.rich_message = False
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    data = FoodMenuNotificationDayCallback(weekday=2, meal=meal)
    with i18n.context(), i18n.use_locale("ru"):
        await on_open_food_menu_notifications(callback, service)
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        selected = next(
            button for row in keyboard.inline_keyboard for button in row if button.callback_data == data.pack()
        )
        assert selected.text == "✅"
        await session.commit()
        session.expire_all()
        await on_toggle_food_menu_notification_day(callback, data, service)
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        selected = next(
            button for row in keyboard.inline_keyboard for button in row if button.callback_data == data.pack()
        )
        assert selected.text == "❌"
    await session.commit()
    session.expire_all()
    summary = await service.get_settings(960001)
    assert getattr(summary.days[2], f"{meal.value}_enabled") is False
    assert callback.answer.await_count == 2


@pytest.mark.parametrize(
    "action,args",
    [
        ("get_settings", ()),
        ("toggle", (0, FoodMenuMeal.LUNCH)),
        ("toggle_weekday", (0,)),
        ("toggle_meal", (FoodMenuMeal.DINNER,)),
        ("enable_all", ()),
        ("disable_all", ()),
    ],
)
async def test_notification_settings_require_an_existing_user(session, action, args):
    service = FoodMenuNotificationSettingsService(
        FoodMenuNotificationSettingsRepository(session), UsersQuery(UserRepository(session))
    )
    with pytest.raises(UserNotFoundError) as error:
        await getattr(service, action)(960099, *args)
    assert error.value.user_id == 960099


@pytest.mark.parametrize("meal", ["lunch", "dinner"])
async def test_recipients_default_enabled_and_filter_only_requested_weekday(session, meal):
    session.add_all([User(id=user_id, full_name="Menu recipient") for user_id in (960011, 960012, 960013)])
    await session.flush()
    repository = FoodMenuNotificationSettingsRepository(session)
    row = await repository.get_or_create(960012, 2)
    setattr(row, f"{meal}_enabled", False)
    other_day = await repository.get_or_create(960013, 3)
    setattr(other_day, f"{meal}_enabled", False)
    recipients = await getattr(repository, f"get_user_ids_with_{meal}_enabled_for_weekday")(2)
    assert {960011, 960013}.issubset(recipients)
    assert 960012 not in recipients


@pytest.mark.parametrize("meal", ["lunch", "dinner"])
@pytest.mark.parametrize("missing", [False, True])
async def test_broadcast_job_selects_today_and_skips_missing_menu(monkeypatch, meal, missing):
    menu = DailyMenuModel(uuid.uuid4(), date(2026, 10, 25), [], 0, 0, 0)
    daily, users, settings, cleanup = (AsyncMock() for _ in range(4))
    daily.get_daily_menu_by_skipping_days.return_value = menu
    if missing:
        daily.get_daily_menu_by_skipping_days.side_effect = DailyMenuNotFoundError(menu.date)
    select_recipients = getattr(settings, f"get_user_ids_with_{meal}_enabled_for_weekday")
    select_recipients.return_value = [960011]
    dependencies = {
        BroadcastFoodMenu: BroadcastFoodMenu(daily, settings),
        LocaleService: users,
        ThemeService: AsyncMock(get_theme=AsyncMock(return_value=Theme.BASIC)),
        FoodMenuCleanupSettingsService: cleanup,
    }

    @asynccontextmanager
    async def container():
        yield SimpleNamespace(get=AsyncMock(side_effect=dependencies.__getitem__))

    send = AsyncMock()
    sender = SimpleNamespace(send=send)
    monkeypatch.setattr(jobs, "TelegramFoodMenuSender", lambda *_: sender)
    await getattr(jobs, f"broadcast_{meal}_menu_job")(container, "bot")
    daily.get_daily_menu_by_skipping_days.assert_awaited_once_with(0)
    if missing:
        select_recipients.assert_not_awaited()
        send.assert_not_awaited()
    else:
        select_recipients.assert_awaited_once_with(
            broadcast_module.datetime.now(broadcast_module.BISHKEK_TZ).date().weekday()
        )
        send.assert_awaited_once_with(menu, 960011)


@pytest.mark.parametrize("stage", ["locale", "theme", "send", "cleanup"])
@pytest.mark.parametrize("telegram_error", [False, True])
async def test_broadcast_delivery_exception_boundary(stage, telegram_error):
    bot, users, cleanup = AsyncMock(), AsyncMock(), AsyncMock()
    users.get_locale.return_value = Locale.RU
    themes = AsyncMock(get_theme=AsyncMock(return_value=Theme.BASIC))
    bot.send_rich_message.return_value = SimpleNamespace(message_id=42)
    error = (
        TelegramBadRequest(method=SendMessage(chat_id=1, text="x"), message="fixture failure")
        if telegram_error
        else RuntimeError("fixture failure")
    )
    failing = {
        "locale": users.get_locale,
        "theme": themes.get_theme,
        "send": bot.send_rich_message,
        "cleanup": cleanup.schedule_cleanup,
    }[stage]
    success = {"locale": Locale.RU, "theme": Theme.BASIC, "send": SimpleNamespace(message_id=42), "cleanup": None}[
        stage
    ]
    failing.side_effect = [error, success]
    menu = DailyMenuModel(uuid.uuid4(), date(2026, 10, 25), [], 0, 0, 0)
    if telegram_error:
        for user_id in [1, 2]:
            await TelegramFoodMenuSender(bot, users, cleanup, themes).send(menu, user_id)
        assert users.get_locale.await_count == 2
        assert bot.send_rich_message.await_args_list[-1].kwargs["chat_id"] == 2
        cleanup.schedule_cleanup.assert_any_await(2, [42])
    else:
        with pytest.raises(RuntimeError, match="fixture failure"):
            for user_id in [1, 2]:
                await TelegramFoodMenuSender(bot, users, cleanup, themes).send(menu, user_id)
        assert users.get_locale.await_count == 1


async def test_sync_normalized_names_preserve_existing_dishes_and_replace_changed_menu(session):
    menus = DailyMenuRepository(session)
    service = FoodMenuSyncService(AsyncMock(), AsyncMock(), menus, DishRepository(session))
    day = date(2098, 2, 1)
    await service._synchronize_daily_menu(ScrapedDailyMenu(day, [ScrapedDish("Soup", "https://example.com/a", 100)]))
    await session.flush()
    original = await menus.get_by_date(day)
    original_id = original.id
    await service._synchronize_daily_menu(ScrapedDailyMenu(day, [ScrapedDish(" SOUP ", "https://example.com/b", 200)]))
    assert original.dishes[0].name == "Soup" and original.dishes[0].calories == 100
    await service._synchronize_daily_menu(ScrapedDailyMenu(day, [ScrapedDish("Rice", "https://example.com/c", 300)]))
    assert original.id == original_id and original.views_count == 0
    assert [dish.name for dish in original.dishes] == ["Rice"]


async def test_food_menu_provider_preserves_app_and_request_lifetimes():
    async with make_async_container(
        CoreProvider(),
        TelegramPlatformProvider(),
        ObisProvider(),
        EdersProvider(),
        StudyWeekProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        UsersProvider(),
        FoodMenuProvider(),
    ) as container:
        client = await container.get(FoodMenuClient)
        parser = await container.get(FoodMenuParser)
        async with container() as request:
            first = await request.get(BroadcastFoodMenu)
            assert first is await request.get(BroadcastFoodMenu)
            assert client is await request.get(FoodMenuClient)
            assert parser is await request.get(FoodMenuParser)
            await request.get(FoodMenuSyncService)
            await request.get(FoodMenuNotificationSettingsService)
        async with container() as request:
            assert first is not await request.get(BroadcastFoodMenu)
            assert client is await request.get(FoodMenuClient)
            assert parser is await request.get(FoodMenuParser)


def test_food_menu_scheduler_keeps_intervals_and_bishkek_cron():
    scheduler = create_scheduler("container", "bot")
    configured = {job.func: job for job in scheduler.get_jobs()}
    assert configured[jobs.sync_daily_menus_job].trigger.interval.total_seconds() == 600
    for handler, hour in [(jobs.broadcast_lunch_menu_job, "11"), (jobs.broadcast_dinner_menu_job, "17")]:
        trigger = configured[handler].trigger
        assert str(trigger.timezone) == "Asia/Bishkek"
        fields = {field.name: str(field) for field in trigger.fields}
        assert fields["hour"] == hour and fields["minute"] == "0"
