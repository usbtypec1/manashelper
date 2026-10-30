import uuid
from dataclasses import replace
from datetime import date
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import PhotoSize, RichMessage

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.eders.application.tracking import EdersEvent
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.modules.food_menu.application.daily_menu import DailyMenuModel, DishModel
from manashelper.modules.food_menu.presentation.callbacks import FoodMenuRatingCallback
from manashelper.modules.food_menu.presentation.food_menu_formatter import (
    build_daily_menu_rich_message,
    build_menu_day_selection,
    format_daily_menu,
    format_not_found,
    refresh_daily_menu_rating,
)
from manashelper.modules.food_menu.presentation.keyboards.food_menu import (
    build_food_menu_settings_buttons,
    build_menu_day_buttons,
    build_menu_rating_buttons,
)
from manashelper.modules.food_menu.presentation.sender import TelegramFoodMenuSender
from manashelper.modules.obis.application.notification import ExamGradeChange, LessonSkipChange, SkipType
from manashelper.modules.obis.presentation.sender import TelegramObisNotificationSender
from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.presentation.sender import TelegramScheduleChangeSender
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.platform.i18n.catalog import i18n
from tests.modules.eders.factories import NOW, item


@pytest.fixture
def menu():
    return DailyMenuModel(
        uuid.uuid4(),
        date(2026, 10, 31),
        [
            DishModel(uuid.uuid4(), "Soup <b>& rice 🎃", "https://example.com/soup.jpg", 150),
            DishModel(uuid.uuid4(), "Salad", "https://example.com/salad.jpg", 100),
        ],
        average_rating=4.5,
        ratings_count=2,
        views_count=7,
        user_rating=4,
    )


def build_menu(menu):
    return build_daily_menu_rich_message(
        menu,
        build_menu_rating_buttons(menu.id, menu.user_rating),
        build_food_menu_settings_buttons(include_notifications=True),
    )


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("theme", list(Theme))
def test_food_theme_covers_message_and_controls_without_changing_data(menu, locale, theme):
    with i18n.context(), i18n.use_locale(locale.value), i18n.use_theme(theme):
        rich = build_menu(menu)
        text = "\n".join(block.text for block in rich.blocks if hasattr(block, "text"))
        assert rich.blocks[0].text.startswith("🎃 ") == (theme == Theme.HALLOWEEN)
        assert "31.10.2026" in text
        assert "Soup <b>& rice 🎃" in text and "Salad" in text
        assert all(
            value in text for value in ["150", "100", "250", "4.5", "（2）" if locale == Locale.ZH else "(2)", "7"]
        )
        assert [photo.photo.media for photo in rich.blocks[1].blocks] == [dish.photo_url for dish in menu.dishes]
        rating = next(block for block in rich.blocks if block.type == "buttons" and len(block.buttons) == 5)
        assert rating.buttons[3].style == "success"
        assert [FoodMenuRatingCallback.unpack(button.callback_data).rating for button in rating.buttons] == [
            1,
            2,
            3,
            4,
            5,
        ]
        assert rating.buttons[0].text == ("🎃 1" if theme == Theme.HALLOWEEN else "1️⃣")
        plain = format_daily_menu(menu)
        assert "Soup &lt;b&gt;&amp; rice 🎃" in plain
        assert "250" in plain
        picker = build_menu_day_selection(build_menu_day_buttons([menu.date], menu.date))
        assert picker.blocks[0].text.startswith("🎃 ") == (theme == Theme.HALLOWEEN)
        assert format_not_found(0).startswith("🕯️ ") == (theme == Theme.HALLOWEEN)
        assert format_not_found(1).startswith("🕯️ ") == (theme == Theme.HALLOWEEN)


def test_rich_rating_refresh_keeps_themed_menu_and_cached_photos(menu):
    with i18n.context(), i18n.use_locale("ru"), i18n.use_theme(Theme.HALLOWEEN):
        outgoing = build_menu(menu)
        data = outgoing.model_dump()
        for index, photo in enumerate(data["blocks"][1]["blocks"]):
            photo["photo"] = [
                PhotoSize(file_id=f"cached-{index}", file_unique_id=str(index), width=640, height=480).model_dump()
            ]
        received = RichMessage.model_validate(data)
        menu = replace(menu, average_rating=3.5, ratings_count=3, user_rating=5)
        refreshed = refresh_daily_menu_rating(received, menu, build_menu_rating_buttons(menu.id, menu.user_rating))
        assert refreshed.blocks[0].text == outgoing.blocks[0].text
        assert [photo.photo.media for photo in refreshed.blocks[1].blocks] == ["cached-0", "cached-1"]
        assert "🍬 Оценка угощений: 3.5 (3)" in [block.text for block in refreshed.blocks if hasattr(block, "text")]
        ratings = next(block for block in refreshed.blocks if block.type == "buttons" and len(block.buttons) == 5)
        assert ratings.buttons[-1].text == "🎃 5" and ratings.buttons[-1].style == "success"
        bot = Bot(token="123456:development-placeholder")
        payload = bot.session.prepare_value(refreshed, bot=bot, files={}, _dumps_json=False)
        assert payload["skip_entity_detection"] is True
        assert payload["blocks"][0]["text"].startswith("🎃 Меню ведьминой кухни")


def test_explicit_locale_uses_that_locales_themed_catalog():
    with i18n.context(), i18n.use_locale("ru"), i18n.use_theme(Theme.HALLOWEEN):
        assert i18n.gettext("food.day_selection_title", locale="en") == "🎃 Halloween kitchen"
        assert i18n.gettext("food.day_selection_title", locale="zh") == "🎃 万圣节厨房"
        assert i18n.gettext("food.day_selection_title", locale="unsupported") == "🎃 Halloween kitchen"
        assert i18n.gettext("eders.submitted") == "Сдано (для теста: попытка завершена)"


@pytest.mark.parametrize("source", ["food", "schedule", "obis", "eders"])
async def test_background_delivery_uses_each_recipients_saved_theme_and_restores_context(session, menu, source):
    session.add_all(
        [
            User(id=982001, full_name="Halloween", locale="ru", theme="halloween"),
            User(id=982002, full_name="Basic", locale="ru", theme="basic"),
        ]
    )
    await session.flush()
    repository = UserRepository(session)
    locales, themes = LocaleService(repository), ThemeService(repository)
    bot, cleanup = AsyncMock(), AsyncMock()
    bot.send_rich_message.return_value.message_id = 42
    with i18n.context(), i18n.use_locale("en"), i18n.use_theme(Theme.HALLOWEEN):
        for user_id in [982001, 982002, 982001]:
            if source == "food":
                await TelegramFoodMenuSender(bot, locales, cleanup, themes).send(menu, user_id)
            elif source == "schedule":
                await TelegramScheduleChangeSender(bot, locales, themes).send(
                    user_id, [LessonChange(1, "09:00-09:50", "Old", "New")]
                )
            elif source == "obis":
                sender = TelegramObisNotificationSender(
                    bot, user_id, await locales.get_locale(user_id), await themes.get_theme(user_id)
                )
                await sender.exam_grade_changed(ExamGradeChange("Math", "Exam", "85"))
                await sender.lesson_skips_changed(LessonSkipChange("Math", SkipType.THEORY, 12.5, 2))
            else:
                event = EdersEvent("opened", item(), "opened", NOW, NOW)
                delivered = [
                    entry
                    async for entry in TelegramEdersNotificationSender(bot, themes).send(
                        user_id, await locales.get_locale(user_id), [event]
                    )
                ]
                assert delivered == [event]
            assert i18n.current_theme == Theme.HALLOWEEN and i18n.current_locale == "en"
    if source == "food":
        messages = [call.kwargs["rich_message"].blocks[0].text for call in bot.send_rich_message.await_args_list]
        assert [message.startswith("🎃 ") for message in messages] == [True, False, True]
        assert cleanup.schedule_cleanup.await_count == 3
    else:
        messages = [call.args[1] for call in bot.send_message.await_args_list]
        if source == "obis":
            assert [message.startswith("🍬 ") for message in messages[::2]] == [True, False, True]
            assert [message.startswith("👻 ") for message in messages[1::2]] == [True, False, True]
        else:
            icon = "🦇 " if source == "schedule" else "🕸️ "
            assert [message.startswith(icon) for message in messages] == [True, False, True]
