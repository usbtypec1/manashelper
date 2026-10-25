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
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.student_questions.provider import StudentQuestionsProvider
from manashelper.modules.student_questions.service import StudentQuestionsService
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.provider import UsersProvider
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
from manashelper.services.obis import UserHasNoCredentialsError
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
    message.text = "/eders"
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
    container = make_async_container(
        AppProvider(),
        RequestProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        StudentQuestionsProvider(),
        UsersProvider(),
    )
    bot = Bot(token="123456789:test-token")
    try:
        dispatcher = create_dispatcher(container)
        assert "eders" in {router.name for router in dispatcher.sub_routers}
        router_names = [router.name for router in dispatcher.sub_routers]
        assert router_names.index("student_questions") < router_names.index("advertisement_contact")
        assert router_names.index("student_questions") < router_names.index("start")
        async with container() as request:
            assert isinstance(await request.get(StudentQuestionsService), StudentQuestionsService)
            assert isinstance(await request.get(EdersService), EdersService)
            assert isinstance(await request.get(StudyWeekService), StudyWeekService)
        scheduler = create_scheduler(container, bot)
        jobs = [job for job in scheduler.get_jobs() if job.func == poll_eders_job]
        assert len(jobs) == 1 and jobs[0].trigger.interval == timedelta(minutes=30)
        assert jobs[0].max_instances == 1
    finally:
        await container.close()
        await bot.session.close()


async def test_materials_search_keeps_matching_course_and_section_in_cached_view() -> None:
    from dataclasses import replace

    service, tracking = AsyncMock(), AsyncMock()
    data = snapshot()
    reading = replace(data.activities[0], id=21, kind=ActivityKind.RESOURCE, name="Arrays", section="Week 5")
    service.get_snapshot.return_value = replace(data, activities=(*data.activities, reading))
    tracking.get_settings.return_value = SimpleNamespace(hide_archived=True)
    message = AsyncMock(spec=Message)
    message.from_user = SimpleNamespace(id=1)
    message.text = "/materials Week 5"
    message.answer = AsyncMock()
    context = state()
    await on_eders_command(message, context, service, tracking)
    assert (await context.get_data())[SNAPSHOT_KEY].activities == (reading,)
    text = message.answer.call_args.args[0]
    assert "Arrays" in text and "Week 5" in text and "Submission:" not in text


async def test_job_groups_new_materials_and_acknowledges_all_events_only_on_success() -> None:
    service, tracking, locales = AsyncMock(), AsyncMock(), AsyncMock()
    tracking.get_poll_user_ids.return_value = [1]
    now = datetime.now(UTC)
    first = EdersEvent("first", snapshot().activities[0], "material_new", now, now)
    second = EdersEvent("second", snapshot().activities[0], "material_changed", now, now)
    tracking.pending_events.return_value = [first, second]
    locales.get_locale.return_value = Locale.EN
    dependencies = {EdersService: service, EdersTrackingService: tracking, LocaleService: locales}

    @asynccontextmanager
    async def scope():
        yield SimpleNamespace(get=AsyncMock(side_effect=lambda cls: dependencies[cls]))

    bot = AsyncMock(spec=Bot)
    bot.send_message.side_effect = TelegramBadRequest(method=SendMessage(chat_id=1, text="test"), message="failure")
    await poll_eders_job(scope, bot)
    tracking.mark_sent.assert_not_awaited()
    bot.send_message.side_effect = None
    bot.send_message.reset_mock()
    await poll_eders_job(scope, bot)
    bot.send_message.assert_awaited_once()
    assert [call.args[1] for call in tracking.mark_sent.await_args_list] == ["first", "second"]


async def test_eders_settings_open_from_notifications_and_keep_return_path_after_toggle() -> None:
    from manashelper.bot.callback_data import EdersSettingCallback, SettingsAction, SettingsCallback
    from manashelper.bot.keyboards.settings import build_settings_keyboard
    from manashelper.bot.routers.eders import on_eders_setting, on_open_eders_settings
    from manashelper.modules.notifications.keyboards import build_notifications_keyboard
    from manashelper.modules.notifications.settings import NotificationSettingsSummary
    from manashelper.services.eders_tracking import EdersSetting, EdersSettings

    main = build_settings_keyboard()
    assert any(
        button.callback_data == SettingsCallback(action=SettingsAction.OPEN_NOTIFICATIONS).pack()
        for row in main.inline_keyboard
        for button in row
    )
    notifications = build_notifications_keyboard(NotificationSettingsSummary(True, True, True))
    entry = next(
        button
        for row in notifications.inline_keyboard
        for button in row
        if button.callback_data == SettingsCallback(action=SettingsAction.OPEN_EDERS_NOTIFICATIONS).pack()
    )
    assert entry.text == "Eders"
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = SimpleNamespace(id=42)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    tracking = AsyncMock()
    tracking.get_settings.return_value = EdersSettings(True, True, True, True, True)
    tracking.toggle.return_value = EdersSettings(False, True, True, True, True)
    await on_open_eders_settings(callback, tracking)
    tracking.get_settings.assert_awaited_once_with(42)
    for selected in (None, EdersSetting.DAY_BEFORE):
        if selected:
            await on_eders_setting(callback, EdersSettingCallback(setting=selected), tracking)
        keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
        assert (
            keyboard.inline_keyboard[-1][0].callback_data
            == SettingsCallback(action=SettingsAction.BACK_TO_NOTIFICATIONS).pack()
        )
        assert len(keyboard.inline_keyboard) == len(EdersSetting) + 1
    tracking.toggle.assert_awaited_once_with(42, EdersSetting.DAY_BEFORE)
    assert callback.message.edit_text.call_args.kwargs["reply_markup"].inline_keyboard[0][0].text.startswith("⬜")


async def test_open_eders_settings_for_unknown_user_shows_alert() -> None:
    from manashelper.bot.routers.eders import on_open_eders_settings
    from manashelper.services.obis import UserNotFoundError

    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = SimpleNamespace(id=42)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    tracking = AsyncMock()
    tracking.get_settings.side_effect = UserNotFoundError(42)
    await on_open_eders_settings(callback, tracking)
    callback.message.edit_text.assert_not_awaited()
    assert callback.answer.call_args.kwargs["show_alert"] is True
