from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Message
from dishka import make_async_container

from manashelper.bot.callback_data import EdersPageCallback
from manashelper.bot.dispatcher import create_dispatcher
from manashelper.bot.routers.eders import SNAPSHOT_KEY, on_eders_command, on_eders_page
from manashelper.di import AppProvider, RequestProvider
from manashelper.jobs.eders import poll_eders_job
from manashelper.jobs.scheduler import create_scheduler
from manashelper.localization.i18n import i18n
from manashelper.localization.locale import Locale
from manashelper.scraping.eders_parser import EdersParseError
from manashelper.services.eders import EdersService
from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    DeadlineFilter,
    EdersActivity,
    EdersCourse,
    EdersSnapshot,
)
from manashelper.services.eders_tracking import EdersEvent, EdersTrackingService
from manashelper.services.locale import LocaleService
from manashelper.services.obis import UserHasNoCredentialsError
from manashelper.services.schedule import NoTrackedCoursesError
from manashelper.services.study_week import StudyWeekService


def snapshot() -> EdersSnapshot:
    now = datetime.now(UTC)
    item = EdersActivity(
        20,
        EdersCourse(10, "Course"),
        ActivityKind.ASSIGNMENT,
        "Work",
        "https://eders.manas.edu.kg/mod/assign/view.php?id=20",
        closes=ActivityDate(now + timedelta(days=1)),
    )
    return EdersSnapshot((item,), now)


def state() -> FSMContext:
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.fixture(autouse=True)
def english():
    with i18n.context(), i18n.use_locale("en"):
        yield


async def test_command_caches_public_snapshot_and_pagination_avoids_network() -> None:
    service, tracking = AsyncMock(), AsyncMock()
    data = snapshot()
    service.get_snapshot.return_value = data
    tracking.get_settings.return_value = SimpleNamespace(hide_archived=True)
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    message.from_user = SimpleNamespace(id=1)
    context = state()
    await on_eders_command(message, context, service, tracking)
    assert (await context.get_data())[SNAPSHOT_KEY] == data
    assert "/mod/assign/view.php?id=20" in message.answer.call_args.args[0]
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = SimpleNamespace(id=1)
    callback.message = message
    await on_eders_page(
        callback, EdersPageCallback(selected=DeadlineFilter.NEXT_SEVEN_DAYS, page=999), context, tracking
    )
    service.get_snapshot.assert_awaited_once_with(1)
    assert "item 1/1" in message.edit_text.call_args.args[0]
    callback.answer.assert_awaited_once()


async def test_missing_credentials_clear_previous_snapshot_and_show_login_button() -> None:
    service, tracking = AsyncMock(), AsyncMock()
    service.get_snapshot.side_effect = UserHasNoCredentialsError(1)
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.from_user = SimpleNamespace(id=1)
    context = state()
    await context.update_data({SNAPSHOT_KEY: snapshot()})
    await on_eders_command(message, context, service, tracking)
    assert (await context.get_data())[SNAPSHOT_KEY] is None
    assert message.answer.call_args.kwargs["reply_markup"].inline_keyboard


async def test_expired_callback_never_uses_previous_results() -> None:
    context = state()
    old = EdersSnapshot(snapshot().activities, datetime.now(UTC) - timedelta(hours=1))
    await context.update_data({SNAPSHOT_KEY: old})
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    tracking = AsyncMock()
    await on_eders_page(callback, EdersPageCallback(selected=DeadlineFilter.ALL), context, tracking)
    callback.answer.assert_awaited_once_with("This list has expired. Run /eders again.", show_alert=True)
    tracking.get_settings.assert_not_awaited()


async def test_week_without_tracked_courses_keeps_eders_dates() -> None:
    eders, schedule = AsyncMock(), AsyncMock()
    eders.get_snapshot.return_value = snapshot()
    schedule.get_user_schedule.side_effect = NoTrackedCoursesError(1)
    result = await StudyWeekService(eders, schedule).get_week(1)
    assert result.lessons == () and not result.has_tracked_courses
    assert len(result.snapshot.activities) == 1


async def test_job_isolates_failed_fetch_and_send_and_uses_recipient_locale() -> None:
    service, tracking, locales, bot = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    tracking.get_poll_user_ids.return_value = [1, 2, 3]
    data = snapshot()
    event = EdersEvent("key", data.activities[0], "before_2", data.activities[0].closes.instant, data.fetched_at)

    async def fetch(user_id):
        if user_id == 2:
            raise EdersParseError("Changed markup")
        return data

    async def recipient_locale(user_id):
        return Locale.RU if user_id == 1 else Locale.ZH

    service.get_snapshot.side_effect = fetch
    locales.get_locale.side_effect = recipient_locale
    tracking.pending_events.return_value = [event]
    bot.send_message.side_effect = [TelegramBadRequest(SendMessage(chat_id=1, text="test"), "test failure"), None]
    dependencies = {EdersService: service, EdersTrackingService: tracking, LocaleService: locales}

    class Request:
        async def get(self, dependency):
            return dependencies[dependency]

    @asynccontextmanager
    async def container():
        yield Request()

    await poll_eders_job(container, bot)
    assert [call.args[0] for call in bot.send_message.await_args_list] == [1, 3]
    assert "Напоминание eders" in bot.send_message.await_args_list[0].args[1]
    assert "eders 截止提醒" in bot.send_message.await_args_list[1].args[1]
    assert tracking.mark_sent.await_count == 1 and tracking.mark_sent.call_args.args[:2] == (3, "key")


async def test_application_resolves_new_services_and_registers_thirty_minute_polling() -> None:
    container = make_async_container(AppProvider(), RequestProvider())
    bot = Bot(token="123456789:test-token")
    try:
        dispatcher = create_dispatcher(container)
        assert "eders" in {router.name for router in dispatcher.sub_routers}
        async with container() as request:
            assert isinstance(await request.get(EdersService), EdersService)
            assert isinstance(await request.get(StudyWeekService), StudyWeekService)
        scheduler = create_scheduler(container, bot)
        jobs = [job for job in scheduler.get_jobs() if job.func == poll_eders_job]
        assert len(jobs) == 1 and jobs[0].trigger.interval == timedelta(minutes=30)
        assert jobs[0].max_instances == 1
    finally:
        await container.close()
        await bot.session.close()
