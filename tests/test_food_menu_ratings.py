import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PhotoSize,
    RichBlockButtons,
    RichBlockCollage,
    RichBlockPhoto,
    RichMessage,
)
from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.bot.callback_data import (
    FoodMenuCleanupOpenCallback,
    FoodMenuRatingCallback,
    SettingsAction,
    SettingsCallback,
)
from manashelper.bot.keyboards.food_menu import build_food_menu_settings_buttons, build_menu_rating_buttons
from manashelper.bot.routers.food_menu import _send_daily_menu, on_food_menu_rating_callback
from manashelper.db.models import DailyMenu, DailyMenuRating, Dish, User
from manashelper.jobs.food_menu import _send_daily_menu_broadcast
from manashelper.localization.i18n import i18n
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.services.daily_menu import DailyMenuModel, DailyMenuService, DishModel
from manashelper.services.food_menu_formatter import build_daily_menu_rich_message, refresh_daily_menu_rating


def _service(session: AsyncSession) -> DailyMenuService:
    return DailyMenuService(DailyMenuRepository(session), DailyMenuRatingRepository(session))


async def _seed(session: AsyncSession) -> tuple[DailyMenu, DailyMenu]:
    dishes = [
        Dish(id=uuid.uuid4(), name=f"dish-{uuid.uuid4()}", calories=200, photo_url="https://example.com/dish.jpg")
        for _ in range(2)
    ]
    menus = [
        DailyMenu(id=uuid.uuid4(), date=date(2090, 1, 1) + timedelta(days=offset), dishes=dishes, views_count=0)
        for offset in range(2)
    ]
    session.add_all([User(id=user_id, full_name="Rating tester") for user_id in (900_001, 900_002)])
    session.add_all(menus)
    await session.flush()
    return menus[0], menus[1]


async def test_one_rating_per_daily_menu_and_user_can_be_changed(session: AsyncSession) -> None:
    first, second = await _seed(session)
    service = _service(session)
    await service.set_rating(900_001, first.id, 5)
    initial = await service.set_rating(900_002, first.id, 1)
    await service.set_rating(900_001, second.id, 2)
    assert initial.average_rating == 3
    assert initial.ratings_count == 2
    assert initial.views_count == 0

    refreshed = await service.set_rating(900_001, first.id, 3)
    assert refreshed.average_rating == 2
    assert refreshed.ratings_count == 2
    assert refreshed.user_rating == 3
    assert refreshed.views_count == 0
    assert len(refreshed.dishes) == 2
    other_day = await service.get_daily_menu_by_date(second.date, user_id=900_001)
    assert other_day.average_rating == 2
    assert other_day.ratings_count == 1
    ratings = await session.scalars(
        select(DailyMenuRating).where(DailyMenuRating.daily_menu_id.in_([first.id, second.id]))
    )
    assert len(ratings.all()) == 3


@pytest.mark.parametrize("score", [0, 6, -1])
async def test_invalid_rating_is_rejected(session: AsyncSession, score: int) -> None:
    first, _ = await _seed(session)
    with pytest.raises(ValueError):
        await _service(session).set_rating(900_001, first.id, score)
    assert not (await session.scalars(select(DailyMenuRating).where(DailyMenuRating.daily_menu_id == first.id))).all()


async def test_missing_menu_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await _service(session).set_rating(900_001, uuid.uuid4(), 3)


def _menu() -> DailyMenuModel:
    return DailyMenuModel(
        id=uuid.uuid4(),
        date=date(2026, 10, 1),
        dishes=[
            DishModel(uuid.uuid4(), "Soup <b>& rice", "https://example.com/soup.jpg", 150),
            DishModel(uuid.uuid4(), "Salad", "https://example.com/salad.jpg", 100),
        ],
        average_rating=4,
        ratings_count=2,
        views_count=7,
        user_rating=4,
    )


def _received(menu: DailyMenuModel, *, broadcast: bool = False) -> RichMessage:
    with i18n.context(), i18n.use_locale("en"):
        outgoing = build_daily_menu_rich_message(
            menu,
            build_menu_rating_buttons(menu.id, menu.user_rating),
            build_food_menu_settings_buttons(include_notifications=broadcast),
        )

    def convert(block, path):
        data = block.model_dump()
        if block.type == "photo":
            data["photo"] = [
                PhotoSize(file_id=f"cached-photo-{path}", file_unique_id=path, width=640, height=480).model_dump()
            ]
        elif block.type == "collage":
            data["blocks"] = [convert(child, f"{path}-{index}") for index, child in enumerate(block.blocks)]
        return data

    return RichMessage.model_validate(
        {"blocks": [convert(block, str(index)) for index, block in enumerate(outgoing.blocks)]}
    )


def test_rich_message_has_only_one_rating_row_for_the_whole_menu_and_preserves_photos() -> None:
    menu = _menu()
    with i18n.context(), i18n.use_locale("en"):
        buttons = build_menu_rating_buttons(menu.id, menu.user_rating)
        assert [button.style for button in buttons.buttons] == [None, None, None, "success", None]
        for score, button in enumerate(buttons.buttons, start=1):
            assert len(button.callback_data.encode()) <= 64
            data = FoodMenuRatingCallback.unpack(button.callback_data)
            assert data.daily_menu_id == menu.id
            assert data.rating == score
        received = _received(menu)
        rating_rows = [
            block for block in received.blocks if isinstance(block, RichBlockButtons) and len(block.buttons) == 5
        ]
        assert len(rating_rows) == 1
        collages = [block for block in received.blocks if isinstance(block, RichBlockCollage)]
        assert len(collages) == 1
        assert len(collages[0].blocks) == 2
        assert all(isinstance(block, RichBlockPhoto) for block in collages[0].blocks)
        menu = DailyMenuModel(menu.id, menu.date, menu.dishes, 3.5, 3, 7, 3)
        outgoing = refresh_daily_menu_rating(received, menu, build_menu_rating_buttons(menu.id, menu.user_rating))
        bot = Bot(token="123456:development-placeholder")
        payload = bot.session.prepare_value(outgoing, bot=bot, files={}, _dumps_json=False)
        assert payload["blocks"][2]["text"] == "1. Soup <b>& rice — 150 kcal\n2. Salad — 100 kcal"
        assert [block["photo"]["media"] for block in payload["blocks"][1]["blocks"]] == [
            "cached-photo-1-0",
            "cached-photo-1-1",
        ]
        assert "⭐ Rating: 3.5 (3)" in [block.get("text") for block in payload["blocks"]]
        assert (
            len([block for block in payload["blocks"] if block["type"] == "buttons" and len(block["buttons"]) == 5])
            == 1
        )


@pytest.mark.parametrize("chat_type, selected", [("private", "success"), ("group", None)])
@pytest.mark.parametrize("broadcast", [False, True])
async def test_callback_updates_menu_rating_and_repeated_score_still_answers(
    monkeypatch, chat_type, selected, broadcast: bool
) -> None:
    menu = _menu()
    message = Message(
        message_id=42, date=0, chat=Chat(id=900_001, type=chat_type), rich_message=_received(menu, broadcast=broadcast)
    )
    callback = CallbackQuery(
        id="rating",
        from_user=TelegramUser(id=900_001, is_bot=False, first_name="Tester"),
        chat_instance="chat",
        message=message,
    )
    data = FoodMenuRatingCallback(daily_menu_id=menu.id, rating=4)
    service = AsyncMock()
    service.set_rating.return_value = menu
    edit = AsyncMock()
    answer = AsyncMock()
    monkeypatch.setattr(Message, "edit_text", edit)
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_rating_callback(callback, data, service)
        service.set_rating.assert_awaited_once_with(900_001, menu.id, 4)
        rich = edit.call_args.kwargs["rich_message"]
        rating_row = next(block for block in rich.blocks if block.type == "buttons" and len(block.buttons) == 5)
        assert rating_row.buttons[3].style == selected
        settings_rows = [block for block in rich.blocks if block.type == "buttons" and len(block.buttons) != 5]
        assert len(settings_rows) == (2 if broadcast else 1)
        assert all(len(row.buttons) == 1 for row in settings_rows)
        edit.side_effect = TelegramBadRequest(
            method=EditMessageText(chat_id=900_001, message_id=42), message="message is not modified"
        )
        await on_food_menu_rating_callback(callback, data, service)
    assert answer.await_count == 2


async def test_callback_from_old_menu_message_still_records_rating(monkeypatch) -> None:
    callback = CallbackQuery(
        id="rating", from_user=TelegramUser(id=900_001, is_bot=False, first_name="Tester"), chat_instance="chat"
    )
    data = FoodMenuRatingCallback(daily_menu_id=uuid.uuid4(), rating=5)
    service = AsyncMock()
    answer = AsyncMock()
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_rating_callback(callback, data, service)
    service.set_rating.assert_awaited_once_with(900_001, data.daily_menu_id, 5)
    answer.assert_awaited_once()


async def test_callback_answers_when_menu_cannot_be_rated(monkeypatch) -> None:
    callback = CallbackQuery(
        id="rating", from_user=TelegramUser(id=900_001, is_bot=False, first_name="Tester"), chat_instance="chat"
    )
    service = AsyncMock()
    service.set_rating.side_effect = ValueError("menu unavailable")
    answer = AsyncMock()
    monkeypatch.setattr(CallbackQuery, "answer", answer)
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_rating_callback(
            callback, FoodMenuRatingCallback(daily_menu_id=uuid.uuid4(), rating=6), service
        )
    answer.assert_awaited_once_with("This menu is no longer available for rating.", show_alert=True)


async def test_menu_delivery_and_broadcast_schedule_one_rich_message_for_cleanup() -> None:
    menu = _menu()
    message = AsyncMock()
    message.chat = Chat(id=900_001, type="private")
    message.answer_rich.return_value.message_id = 42
    message.answer_rich.return_value.ephemeral_message_id = None
    service = AsyncMock()
    service.get_daily_menu_by_skipping_days.return_value = menu
    cleanup = AsyncMock()
    with i18n.context(), i18n.use_locale("en"):
        await _send_daily_menu(message, 0, service, cleanup)
    message.answer_rich.assert_awaited_once()
    cleanup.schedule_cleanup.assert_awaited_once_with(900_001, [42])
    requested_rich = message.answer_rich.call_args.kwargs["rich_message"]
    requested_settings = [
        block for block in requested_rich.blocks if block.type == "buttons" and len(block.buttons) != 5
    ]
    assert len(requested_settings) == 1
    assert requested_settings[0].buttons[0].callback_data == FoodMenuCleanupOpenCallback().pack()

    bot = AsyncMock()
    bot.send_rich_message.return_value.message_id = 43
    users = AsyncMock()
    users.get_by_id.return_value.locale = "ru"
    cleanup.reset_mock()
    await _send_daily_menu_broadcast(bot, users, cleanup, menu, [900_001])
    cleanup.schedule_cleanup.assert_awaited_once_with(900_001, [43])
    rich = bot.send_rich_message.call_args.kwargs["rich_message"]
    assert "Меню" in rich.blocks[0].text
    rating_rows = [block for block in rich.blocks if block.type == "buttons" and len(block.buttons) == 5]
    assert len(rating_rows) == 1
    assert all(button.style is None for button in rating_rows[0].buttons)
    broadcast_settings = [block for block in rich.blocks if block.type == "buttons" and len(block.buttons) != 5]
    assert [len(row.buttons) for row in broadcast_settings] == [1, 1]
    assert broadcast_settings[0].buttons[0].callback_data == FoodMenuCleanupOpenCallback().pack()
    assert (
        broadcast_settings[1].buttons[0].callback_data
        == SettingsCallback(action=SettingsAction.OPEN_FOOD_MENU_NOTIFICATIONS).pack()
    )
