import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User
from dishka import make_async_container

from manashelper.core.provider import CoreProvider
from manashelper.db.models import Course, Department, Faculty, NotificationSettings
from manashelper.db.models import User as DbUser
from manashelper.di import RequestProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.notifications.queries import NotificationRecipientsQuery
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule import jobs
from manashelper.modules.schedule.application.course import CourseService, UserNotFoundError
from manashelper.modules.schedule.application.lesson_search import LessonSearchResult
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleService
from manashelper.modules.schedule.application.sync_course import SyncCourseTimetable
from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.infrastructure.timetable_client import TimetableClient
from manashelper.modules.schedule.presentation.callbacks import (
    CourseCallback,
    LessonSearchPageCallback,
    ScheduleDayCallback,
)
from manashelper.modules.schedule.presentation.routers import lesson_search, timetable
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.provider import TelegramPlatformProvider


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=961001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="schedule", from_user=user, message=message, chat_instance="chat").as_(bot)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=user.id, user_id=user.id))
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    with i18n.context(), i18n.use_locale("ru"):
        yield SimpleNamespace(message=message, callback=callback, state=state, request=request)


def test_schedule_callback_fsm_and_private_flags():
    assert CourseCallback(id=123).pack() == "course:123"
    assert ScheduleDayCallback(weekday=2).pack() == "schedule_day:2"
    assert LessonSearchPageCallback(page=1).pack() == "lesson_search_page:1"
    assert lesson_search.LessonSearchForm.query.state == "LessonSearchForm:query"
    assert lesson_search.RESULTS_KEY == "lesson_search_results"
    for router in (timetable.router, lesson_search.router):
        for observer in (router.message, router.callback_query):
            assert all(handler.flags.get("private_chat_only") for handler in observer.handlers)


@pytest.mark.parametrize("day,expected", [(23, 5), (24, 1), (25, 1)])
def test_current_schedule_day_maps_weekend_to_monday(day, expected):
    assert timetable._current_weekday(datetime(2026, 10, day)) == expected


async def test_search_entry_retains_cache_until_query_is_received(context):
    await context.state.update_data(old="kept")
    await lesson_search.on_search_selected(context.callback, context.state)
    assert await context.state.get_state() == "LessonSearchForm:query"
    assert await context.state.get_data() == {"old": "kept"}


@pytest.mark.parametrize("query", [None, "", " x ", "  "])
async def test_short_query_clears_state_and_cache_without_searching(context, query):
    await context.state.set_state(lesson_search.LessonSearchForm.query)
    await context.state.update_data(lesson_search_results=["old"])
    service = AsyncMock()
    await lesson_search.on_search_query_entered(
        context.message.model_copy(update={"text": query}), context.state, service
    )
    assert await context.state.get_state() is None and await context.state.get_data() == {}
    service.search.assert_not_awaited()


@pytest.mark.parametrize("found", [False, True])
async def test_search_trims_query_and_caches_results_without_another_fetch(context, found):
    result = LessonSearchResult(1, 1, "Faculty", "Department", 1, "Analysis", ["09:00-09:50"])
    service = AsyncMock()
    service.search.return_value = [result] if found else []
    message = context.message.model_copy(update={"text": "  Analysis  "})
    await lesson_search.on_search_query_entered(message, context.state, service)
    service.search.assert_awaited_once_with("Analysis")
    assert await context.state.get_state() is None
    assert await context.state.get_data() == ({"lesson_search_results": [result]} if found else {})
    await lesson_search.on_search_page_selected(context.callback, LessonSearchPageCallback(page=0), context.state)
    service.search.assert_awaited_once()


@pytest.mark.parametrize("failure", ["user", "tracking", "empty"])
async def test_schedule_menu_keeps_missing_user_untracked_and_unloaded_paths(context, failure):
    service = AsyncMock()
    if failure == "user":
        service.get_user_schedule.side_effect = UserNotFoundError(961001)
    elif failure == "tracking":
        service.get_user_schedule.side_effect = NoTrackedCoursesError(961001)
    else:
        service.get_user_schedule.return_value = []
    await timetable.on_my_schedule_selected(context.callback, service)
    methods = [call.args[1] for call in context.request.await_args_list]
    assert methods[-1].__class__.__name__ == "AnswerCallbackQuery"
    assert methods[-1].show_alert == (True if failure != "tracking" else None)
    assert len(methods) == (2 if failure == "tracking" else 1)


async def test_schedule_query_sorts_by_weekday_and_numeric_start_time():
    users, lessons = AsyncMock(), AsyncMock()
    users.get_with_tracked_courses.return_value = SimpleNamespace(tracked_courses=[SimpleNamespace(id=2)])
    lessons.get_all_by_course_ids.return_value = [
        SimpleNamespace(weekday=2, time_range="8:00-8:50", content="Tuesday"),
        SimpleNamespace(weekday=1, time_range="10:00-10:50", content="Late"),
        SimpleNamespace(weekday=1, time_range="9:00-9:50", content="Early"),
    ]
    result = await ScheduleService(lessons, users).get_user_schedule(961001)
    assert [lesson.content for lesson in result] == ["Early", "Late", "Tuesday"]
    lessons.get_all_by_course_ids.assert_awaited_once_with([2])


@pytest.mark.parametrize("failure", ["sync", "telegram", "transport", "locale", "unchanged", "recipients"])
async def test_sync_job_keeps_course_scopes_and_failure_isolation(failure):
    courses, sync, notifications, users, bot = (AsyncMock() for _ in range(5))
    courses.get_all_ids.return_value = [1, 2]
    changes = [LessonChange(1, "09:00-09:50", "Old", "New")]
    sync.synchronize_course_timetable.side_effect = [
        RuntimeError("sync failed") if failure == "sync" else ([] if failure == "unchanged" else changes),
        changes,
    ]
    notifications.get_user_ids_tracking_course_with_schedule_changes_enabled.side_effect = lambda course_id: (
        ([] if failure == "recipients" else [10, 11]) if course_id == 1 else [20]
    )

    async def locale(user_id):
        if user_id == 10 and failure == "locale":
            raise ValueError("invalid locale")
        return SimpleNamespace(locale="ru")

    users.get_by_id.side_effect = locale

    async def send(user_id, text):
        if user_id == 10 and failure == "telegram":
            raise TelegramBadRequest(method=SendMessage(chat_id=user_id, text=text), message="unavailable")
        if user_id == 10 and failure == "transport":
            raise RuntimeError("unexpected transport")

    bot.send_message.side_effect = send
    dependencies = {
        CourseService: courses,
        SyncCourseTimetable: SyncCourseTimetable(sync, NotificationRecipientsQuery(notifications)),
        LocaleService: LocaleService(users),
    }
    scopes = []

    @asynccontextmanager
    async def container():
        scopes.append(object())
        yield SimpleNamespace(get=AsyncMock(side_effect=dependencies.__getitem__))

    await jobs.sync_timetable_job(container, bot)
    assert len(scopes) == 3
    assert [call.args[0] for call in sync.synchronize_course_timetable.await_args_list] == [1, 2]
    expected = [10, 11, 20] if failure == "telegram" else ([10, 20] if failure == "transport" else [20])
    assert [call.args[0] for call in bot.send_message.await_args_list] == expected


async def test_schedule_recipient_query_preserves_tracking_and_default_opt_in(session):
    faculty = Faculty(id=uuid.uuid4(), name="Schedule migration")
    department = Department(id=uuid.uuid4(), name="Schedule migration", faculty=faculty)
    course = Course(id=961101, number=1, department=department)
    session.add_all(
        [
            course,
            DbUser(id=961011, full_name="Default enabled", tracked_courses=[course]),
            DbUser(id=961012, full_name="Disabled", tracked_courses=[course]),
            DbUser(id=961013, full_name="No tracking", tracked_courses=[]),
        ]
    )
    await session.flush()
    session.add(NotificationSettings(user_id=961012, schedule_changes_enabled=False))
    await session.flush()
    from manashelper.modules.notifications.repository import NotificationSettingsRepository

    result = await NotificationRecipientsQuery(NotificationSettingsRepository(session)).for_schedule_changes(course.id)
    assert 961011 in result and 961012 not in result and 961013 not in result


async def test_schedule_provider_scopes_and_hourly_job_contract():
    async with make_async_container(
        CoreProvider(),
        TelegramPlatformProvider(),
        ObisProvider(),
        EdersProvider(),
        RequestProvider(),
        ScheduleProvider(),
        NotificationsProvider(),
        UsersProvider(),
    ) as container:
        client = await container.get(TimetableClient)
        async with container() as request:
            first = await request.get(SyncCourseTimetable)
            assert first is await request.get(SyncCourseTimetable)
            assert client is await request.get(TimetableClient)
            await request.get(ScheduleService)
            await request.get(CourseService)
        async with container() as request:
            assert first is not await request.get(SyncCourseTimetable)
            assert client is await request.get(TimetableClient)
    scheduler = create_scheduler("container", "bot")
    registered = [job for job in scheduler.get_jobs() if job.func == jobs.sync_timetable_job]
    assert len(registered) == 1 and registered[0].trigger.interval.total_seconds() == 3600
    assert registered[0].args == ("container", "bot")
