from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter, TelegramServerError
from aiogram.methods import SendMessage
from aiogram.types import Chat, Message
from aiogram.types import User as TelegramUser
from dishka.integrations.aiogram import CONTAINER_NAME
from sqlalchemy import select

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.food_menu.infrastructure.repositories.food_menu_notification_settings_repository import (
    FoodMenuNotificationSettingsRepository,
)
from manashelper.modules.notifications.orm import NotificationSettings
from manashelper.modules.notifications.repository import NotificationSettingsRepository
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.delivery import UserMessageDelivery
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware


async def test_stopped_users_are_excluded_from_every_recipient_selection(session):
    course = await session.scalar(select(Course).limit(1))
    assert course is not None
    active = User(id=946601, full_name="Active", tracked_courses=[course])
    stopped = User(id=946602, full_name="Stopped", bot_stopped=True, tracked_courses=[course])
    session.add_all([active, stopped])
    await session.flush()
    queries = UsersQuery(UserRepository(session))
    assert {active.id, stopped.id} <= set(await queries.get_all_ids())
    assert active.id in await queries.get_active_ids() and stopped.id not in await queries.get_active_ids()
    notifications = NotificationSettingsRepository(session)
    food = FoodMenuNotificationSettingsRepository(session)
    selections = [
        await notifications.get_user_ids_with_exam_grades_enabled(),
        await notifications.get_user_ids_with_lesson_skips_enabled(),
        await notifications.get_user_ids_tracking_course_with_schedule_changes_enabled(course.id),
        await food.get_user_ids_with_lunch_enabled_for_weekday(0),
        await food.get_user_ids_with_dinner_enabled_for_weekday(0),
    ]
    for ids in selections:
        assert active.id in ids and stopped.id not in ids


async def test_private_interaction_resumes_bot_without_changing_preferences(session):
    user = User(id=946603, full_name="Stopped", bot_stopped=True, locale="ru")
    session.add(user)
    await session.flush()
    settings = NotificationSettings(user_id=user.id, schedule_changes_enabled=False, exam_grades_enabled=False)
    session.add(settings)
    await session.flush()
    locales = LocaleService(UserRepository(session))
    await locales.resolve(user.id, "Group activity", None, "en")
    assert user.bot_stopped is True
    await locales.resolve(user.id, "Private activity", None, "en", resume_bot=True)
    assert user.bot_stopped is False and user.locale == "ru"
    assert settings.schedule_changes_enabled is False and settings.exam_grades_enabled is False


@pytest.mark.parametrize("chat_type", ["private", "group", "supergroup", "channel"])
async def test_only_private_updates_request_bot_resumption(chat_type):
    locales = AsyncMock(spec=LocaleService)
    locales.resolve.return_value = Locale.RU
    themes = AsyncMock(spec=ThemeService)
    themes.get_theme.return_value = Theme.BASIC
    request = SimpleNamespace(get=AsyncMock(side_effect={LocaleService: locales, ThemeService: themes}.__getitem__))
    user = TelegramUser(id=42, is_bot=False, first_name="Student")
    chat = Chat(id=42 if chat_type == "private" else -42, type=chat_type)
    message = Message(message_id=1, date=0, chat=chat, from_user=user, text="any input")
    handler = AsyncMock(return_value="handled")
    assert (
        await LocaleMiddleware()(
            handler, message, {CONTAINER_NAME: request, "event_chat": chat, "event_from_user": user}
        )
        == "handled"
    )
    assert locales.resolve.await_args.kwargs["resume_bot"] is (chat_type == "private")


async def test_permanent_failure_persists_flag_and_suppresses_next_attempt(session):
    user_id = 946604
    session.add(User(id=user_id, full_name="Recipient"))
    await session.flush()
    delivery = UserMessageDelivery(BotStatusService(UserRepository(session)))
    send = AsyncMock(
        side_effect=TelegramForbiddenError(
            method=SendMessage(chat_id=user_id, text="test"),
            message="Forbidden: bot was blocked by the user",
        )
    )
    with pytest.raises(TelegramForbiddenError):
        await delivery.send(user_id, send)
    await session.flush()
    session.expire_all()
    assert (await UserRepository(session).get_by_id(user_id)).bot_stopped is True
    assert await delivery.send(user_id, send) is None
    assert send.await_count == 1


@pytest.mark.parametrize(
    "reason",
    ["Forbidden: user is deactivated", "Bad Request: chat not found", "Forbidden: bot was blocked by the user"],
)
async def test_permanent_telegram_errors_mark_user_stopped(reason):
    status = AsyncMock(spec=BotStatusService)
    status.is_stopped.return_value = False
    error = TelegramForbiddenError(method=SendMessage(chat_id=42, text="test"), message=reason)
    with pytest.raises(TelegramForbiddenError):
        await UserMessageDelivery(status).send(42, AsyncMock(side_effect=error))
    status.stop.assert_awaited_once_with(42)


@pytest.mark.parametrize("kind", ["rate_limit", "server", "invalid_content"])
async def test_temporary_or_content_errors_preserve_delivery_eligibility(kind):
    status = AsyncMock(spec=BotStatusService)
    status.is_stopped.return_value = False
    method = SendMessage(chat_id=42, text="test")
    error = (
        TelegramRetryAfter(method=method, message="Too Many Requests", retry_after=1)
        if kind == "rate_limit"
        else TelegramServerError(method=method, message="Internal Server Error")
        if kind == "server"
        else TelegramBadRequest(method=method, message="Bad Request: can't parse entities")
    )
    with pytest.raises(type(error)):
        await UserMessageDelivery(status).send(42, AsyncMock(side_effect=error))
    status.stop.assert_not_awaited()
