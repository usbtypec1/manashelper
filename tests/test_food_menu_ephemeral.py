import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.methods import EditEphemeralMessageText, GetChatMember, SendMessage, SendRichMessage
from aiogram.types import CallbackQuery, Chat, Message, RichMessage, User

from manashelper.bot.callback_data import (
    FoodMenuCallback,
    FoodMenuDateCallback,
    FoodMenuDay,
    FoodMenuOpenCallback,
    FoodMenuRatingCallback,
)
from manashelper.bot.keyboards.food_menu import build_menu_rating_buttons
from manashelper.bot.routers.food_menu import (
    cmd_yemek,
    on_food_menu_date_callback,
    on_food_menu_day_callback,
    on_food_menu_open_callback,
    on_food_menu_rating_callback,
)
from manashelper.localization.i18n import i18n
from manashelper.services.daily_menu import DailyMenuAvailability, DailyMenuModel, DailyMenuNotFoundError
from manashelper.services.food_menu_formatter import build_daily_menu_rich_message

USER = User(id=900_001, is_bot=False, first_name="Tester")
CHAT_ID = -900_001


def _menu() -> DailyMenuModel:
    return DailyMenuModel(uuid.uuid4(), date(2026, 10, 1), [], 4, 1, 7, 4)


def _bot(monkeypatch, *, administrator: bool = False):
    bot = Bot(token="123456:development-placeholder")

    async def respond(_bot, method, **kwargs):
        if isinstance(method, GetChatMember):
            return SimpleNamespace(status="administrator" if administrator else "member")
        if isinstance(method, (SendMessage, SendRichMessage)):
            ephemeral = method.ephemeral_message_parameters is not None
            return Message(
                message_id=0 if ephemeral else 42,
                ephemeral_message_id=88 if ephemeral else None,
                receiver_user=USER if ephemeral else None,
                date=0,
                chat=Chat(id=CHAT_ID, type="supergroup"),
            ).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    return bot, request


def _methods(request, method_type):
    return [call.args[1] for call in request.await_args_list if isinstance(call.args[1], method_type)]


@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
@pytest.mark.parametrize("source", ["ephemeral", "administrator"])
@pytest.mark.parametrize("found", [False, True])
async def test_group_command_sends_private_menu_without_regular_cleanup(monkeypatch, chat_type, source, found) -> None:
    bot, request = _bot(monkeypatch, administrator=source == "administrator")
    incoming = Message(
        message_id=0 if source == "ephemeral" else 10,
        ephemeral_message_id=11 if source == "ephemeral" else None,
        from_user=USER,
        date=0,
        chat=Chat(id=CHAT_ID, type=chat_type),
        text="/yemek today",
    ).as_(bot)
    service, cleanup = AsyncMock(), AsyncMock()
    menu = _menu()
    if found:
        service.get_daily_menu_by_skipping_days.return_value = menu
    else:
        service.get_daily_menu_by_skipping_days.side_effect = DailyMenuNotFoundError(menu.date)
    with i18n.context(), i18n.use_locale("en"):
        await cmd_yemek(incoming, CommandObject(command="yemek", args="today"), service, cleanup)
    service.get_daily_menu_by_skipping_days.assert_awaited_once_with(0, user_id=USER.id)
    sent = _methods(request, SendRichMessage if found else SendMessage)[0]
    assert sent.chat_id == CHAT_ID
    assert sent.ephemeral_message_parameters.receiver_user_id == USER.id
    assert sent.ephemeral_message_parameters.callback_query_id is None
    if source == "ephemeral":
        assert not _methods(request, GetChatMember)
        assert sent.reply_parameters.ephemeral_message_id == 11
        assert sent.reply_parameters.message_id is None
    else:
        assert _methods(request, GetChatMember)[0].user_id == bot.id
        assert sent.reply_parameters is None
    if found:
        rows = [block for block in sent.rich_message.blocks if block.type == "buttons"]
        assert len(rows) == 1
        assert rows[0].buttons[3].style == "success"
    cleanup.schedule_cleanup.assert_not_awaited()


async def test_ordinary_group_command_uses_day_selector_when_bot_is_not_admin(monkeypatch) -> None:
    bot, request = _bot(monkeypatch)
    incoming = Message(message_id=10, from_user=USER, date=0, chat=Chat(id=CHAT_ID, type="group")).as_(bot)
    service, cleanup = AsyncMock(), AsyncMock()
    with i18n.context(), i18n.use_locale("en"):
        await cmd_yemek(incoming, CommandObject(command="yemek", args="today"), service, cleanup)
    prompt = _methods(request, SendMessage)[0]
    assert prompt.ephemeral_message_parameters is None
    rows = prompt.reply_markup.inline_keyboard
    assert len(rows) == 1
    assert rows[0][0].callback_data == FoodMenuOpenCallback().pack()
    service.get_available_dates.assert_not_awaited()
    service.get_daily_menu_by_skipping_days.assert_not_awaited()
    cleanup.schedule_cleanup.assert_not_awaited()


@pytest.mark.parametrize("existing_ephemeral", [False, True])
@pytest.mark.parametrize("found", [False, True])
async def test_group_day_callback_targets_person_who_clicked_even_when_bot_is_not_admin(
    monkeypatch, existing_ephemeral, found
) -> None:
    bot, request = _bot(monkeypatch)
    prompt = Message(
        message_id=0 if existing_ephemeral else 42,
        ephemeral_message_id=88 if existing_ephemeral else None,
        receiver_user=USER if existing_ephemeral else None,
        from_user=User(id=bot.id, is_bot=True, first_name="Bot"),
        date=0,
        chat=Chat(id=CHAT_ID, type="supergroup"),
    ).as_(bot)
    callback = CallbackQuery(id="pick-day", from_user=USER, chat_instance="chat", message=prompt).as_(bot)
    service, cleanup = AsyncMock(), AsyncMock()
    if found:
        service.get_daily_menu_by_skipping_days.return_value = _menu()
    else:
        service.get_daily_menu_by_skipping_days.side_effect = DailyMenuNotFoundError(date(2026, 10, 2))
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_day_callback(callback, FoodMenuCallback(day=FoodMenuDay.TOMORROW), service, cleanup)
    sent = _methods(request, SendRichMessage if found else SendMessage)[0]
    parameters = sent.ephemeral_message_parameters
    assert parameters.receiver_user_id == USER.id
    assert parameters.callback_query_id == callback.id
    assert parameters.replace_callback_query_message is (not existing_ephemeral)
    service.get_daily_menu_by_skipping_days.assert_awaited_once_with(1, user_id=USER.id)
    assert not _methods(request, GetChatMember)
    cleanup.schedule_cleanup.assert_not_awaited()


@pytest.mark.parametrize("args", [None, "invalid"])
async def test_ephemeral_command_usage_and_day_picker_remain_private(monkeypatch, args) -> None:
    bot, request = _bot(monkeypatch)
    incoming = Message(
        message_id=0,
        ephemeral_message_id=11,
        from_user=USER,
        date=0,
        chat=Chat(id=CHAT_ID, type="group"),
    ).as_(bot)
    service = AsyncMock()
    today = date(2026, 10, 1)
    service.get_available_dates.return_value = DailyMenuAvailability(today, [today, today + timedelta(days=2)])
    with i18n.context(), i18n.use_locale("en"):
        await cmd_yemek(incoming, CommandObject(command="yemek", args=args), service, AsyncMock())
    prompt = _methods(request, SendMessage)[0]
    assert prompt.ephemeral_message_parameters.receiver_user_id == USER.id
    assert prompt.reply_parameters.ephemeral_message_id == 11
    rows = prompt.reply_markup.inline_keyboard
    assert [FoodMenuDateCallback.unpack(row[0].callback_data).menu_date for row in rows] == [
        today.isoformat(),
        (today + timedelta(days=2)).isoformat(),
    ]
    assert prompt.reply_parameters.message_id is None
    assert not _methods(request, GetChatMember)


@pytest.mark.parametrize("days", [0, 1, 3])
async def test_open_button_shows_ephemeral_inline_day_selection_without_admin_rights(monkeypatch, days) -> None:
    bot, request = _bot(monkeypatch)
    message = Message(message_id=42, date=0, chat=Chat(id=CHAT_ID, type="supergroup")).as_(bot)
    callback = CallbackQuery(id="open-menu", from_user=USER, chat_instance="chat", message=message).as_(bot)
    service = AsyncMock()
    today = date(2026, 10, 1)
    dates = [today + timedelta(days=offset) for offset in range(days)]
    service.get_available_dates.return_value = DailyMenuAvailability(today, dates)
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_open_callback(callback, service)
    sent = _methods(request, SendMessage)[0]
    assert sent.ephemeral_message_parameters.receiver_user_id == USER.id
    assert sent.ephemeral_message_parameters.callback_query_id == callback.id
    assert sent.ephemeral_message_parameters.replace_callback_query_message is True
    rows = sent.reply_markup.inline_keyboard if sent.reply_markup else []
    assert [FoodMenuDateCallback.unpack(row[0].callback_data).menu_date for row in rows] == [
        menu_date.isoformat() for menu_date in dates
    ]
    if not days:
        assert "No menus" in sent.text
    assert not _methods(request, GetChatMember)


@pytest.mark.parametrize("chat_type", ["private", "supergroup"])
async def test_date_selection_opens_original_date_even_after_midnight(monkeypatch, chat_type) -> None:
    bot, request = _bot(monkeypatch)
    message = Message(message_id=42, date=0, chat=Chat(id=CHAT_ID, type=chat_type)).as_(bot)
    callback = CallbackQuery(id="pick-date", from_user=USER, chat_instance="chat", message=message).as_(bot)
    service, cleanup = AsyncMock(), AsyncMock()
    menu = _menu()
    service.get_daily_menu_by_date.return_value = menu
    with i18n.context(), i18n.use_locale("en"):
        await on_food_menu_date_callback(callback, FoodMenuDateCallback(menu_date="2026-10-01"), service, cleanup)
    service.get_daily_menu_by_date.assert_awaited_once_with(
        date(2026, 10, 1), user_id=USER.id if chat_type == "supergroup" else CHAT_ID
    )
    service.get_daily_menu_by_skipping_days.assert_not_awaited()
    sent = _methods(request, SendRichMessage)[0]
    if chat_type == "supergroup":
        assert sent.ephemeral_message_parameters.receiver_user_id == USER.id
        cleanup.schedule_cleanup.assert_not_awaited()
    else:
        assert sent.ephemeral_message_parameters is None
        cleanup.schedule_cleanup.assert_awaited_once_with(CHAT_ID, [42])


@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup"])
async def test_day_picker_is_ephemeral_in_groups_and_normal_in_private_chat(monkeypatch, chat_type) -> None:
    bot, request = _bot(monkeypatch, administrator=True)
    incoming = Message(message_id=10, from_user=USER, date=0, chat=Chat(id=CHAT_ID, type=chat_type)).as_(bot)
    service = AsyncMock()
    today = date(2026, 10, 1)
    service.get_available_dates.return_value = DailyMenuAvailability(today, [today])
    with i18n.context(), i18n.use_locale("en"):
        await cmd_yemek(incoming, CommandObject(command="yemek"), service, AsyncMock())
    prompt = _methods(request, SendMessage)[0]
    assert (prompt.ephemeral_message_parameters is None) is (chat_type == "private")
    assert prompt.reply_parameters is None
    rows = prompt.reply_markup.inline_keyboard
    assert rows[0][0].callback_data == FoodMenuDateCallback(menu_date=today.isoformat()).pack()


async def test_ephemeral_rating_uses_ephemeral_edit_and_preserves_personal_selection(monkeypatch) -> None:
    bot, request = _bot(monkeypatch)
    menu = _menu()
    with i18n.context(), i18n.use_locale("en"):
        outgoing = build_daily_menu_rich_message(menu, build_menu_rating_buttons(menu.id), [])
        received = RichMessage.model_validate(outgoing.model_dump())
        message = Message(
            message_id=0,
            ephemeral_message_id=88,
            receiver_user=USER,
            date=0,
            chat=Chat(id=CHAT_ID, type="supergroup"),
            rich_message=received,
        ).as_(bot)
        callback = CallbackQuery(id="rate", from_user=USER, chat_instance="chat", message=message).as_(bot)
        service = AsyncMock()
        service.set_rating.return_value = menu
        await on_food_menu_rating_callback(callback, FoodMenuRatingCallback(daily_menu_id=menu.id, rating=4), service)
    edited = _methods(request, EditEphemeralMessageText)[0]
    assert edited.chat_id == CHAT_ID
    assert edited.receiver_user_id == USER.id
    assert edited.ephemeral_message_id == 88
    row = next(block for block in edited.rich_message.blocks if block.type == "buttons")
    assert row.buttons[3].style == "success"
    service.set_rating.assert_awaited_once_with(USER.id, menu.id, 4)
