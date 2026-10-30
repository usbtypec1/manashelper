from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message
from dishka import make_async_container

from manashelper.core.provider import CoreProvider
from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.eders.application.models import (
    ActivityDate,
    ActivityKind,
    EdersActivity,
    EdersCourse,
    EdersSnapshot,
    SubmissionStatus,
)
from manashelper.modules.eders.errors import EdersFetchError, EdersParseError, EdersUnsafeUrlError
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.errors import ObisLoginError, ObisParseError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleLessonModel
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.study_week import application
from manashelper.modules.study_week.application import GetStudyWeek, StudyWeek, week_end
from manashelper.modules.study_week.formatter import format_study_week
from manashelper.modules.study_week.provider import StudyWeekProvider
from manashelper.modules.study_week.router import on_week_command, router
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n

START = date(2026, 10, 1)
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def activity(**changes):
    return replace(
        EdersActivity(10, EdersCourse(20, "Course"), ActivityKind.ASSIGNMENT, "Work", "https://example.com/?a=1&b=2"),
        **changes,
    )


@pytest.fixture(autouse=True)
def english():
    with i18n.context(), i18n.use_locale("en"):
        yield


@pytest.mark.parametrize("tracked", [True, False])
async def test_week_reads_eders_then_schedule_then_current_bishkek_date(monkeypatch, tracked):
    calls = []
    snapshot = EdersSnapshot((), NOW - timedelta(days=2))
    lessons = [ScheduleLessonModel(4, "9:00-9:50", "Class")]

    async def eders(user_id):
        calls.append(("eders", user_id))
        return snapshot

    async def schedule(user_id):
        calls.append(("schedule", user_id))
        if not tracked:
            raise NoTrackedCoursesError(user_id)
        return lessons

    def now(tz):
        calls.append(("now", tz))
        return datetime(2026, 10, 1, 0, 5, tzinfo=BISHKEK_TZ)

    monkeypatch.setitem(vars(application), "datetime", SimpleNamespace(now=now))
    result = await GetStudyWeek(
        SimpleNamespace(get_snapshot=eders), SimpleNamespace(get_user_schedule=schedule)
    ).execute(42)
    assert calls == [("eders", 42), ("schedule", 42), ("now", BISHKEK_TZ)]
    assert result == StudyWeek(START, tuple(lessons) if tracked else (), snapshot, tracked)
    lessons.clear()
    assert len(result.lessons) == int(tracked)
    assert week_end(result) == date(2026, 10, 7)


@pytest.mark.parametrize("source", ["eders", "schedule"])
async def test_source_failures_propagate_without_returning_partial_week(source):
    eders, schedule = AsyncMock(), AsyncMock()
    eders.get_snapshot.return_value = EdersSnapshot((), NOW)
    error = RuntimeError("source failed")
    getattr(
        eders if source == "eders" else schedule, "get_snapshot" if source == "eders" else "get_user_schedule"
    ).side_effect = error
    with pytest.raises(RuntimeError) as caught:
        await GetStudyWeek(eders, schedule).execute(42)
    assert caught.value is error
    if source == "eders":
        schedule.get_user_schedule.assert_not_awaited()


def test_week_includes_seven_local_days_and_preserves_submitted_and_undated_material_rules():
    first = datetime(2026, 9, 30, 18, tzinfo=UTC)
    last = datetime(2026, 10, 7, 17, 59, tzinfo=UTC)
    items = (
        activity(
            name="first", opens=ActivityDate(first), closes=ActivityDate(last), submission=SubmissionStatus.SUBMITTED
        ),
        activity(name="before", closes=ActivityDate(first - timedelta(minutes=1))),
        activity(name="after", closes=ActivityDate(last + timedelta(minutes=1))),
        activity(name="conflicting", closes=ActivityDate(first, conflict=True)),
        activity(name="unverified", closes=ActivityDate(source_text="01.10.2026")),
        activity(name="resource", kind=ActivityKind.RESOURCE, first_seen=first),
        activity(name="assignment_discovery", first_seen=first),
    )
    text = "\n".join(format_study_week(StudyWeek(START, (), EdersSnapshot(items, NOW), False)))
    assert text.count(">first</a>") == 2 and ">resource</a>" in text
    assert all(
        f">{name}</a>" not in text for name in ("before", "after", "conflicting", "unverified", "assignment_discovery")
    )
    assert "01.10" in text and "07.10" in text and "08.10" not in text
    assert text.count("<b>") == 7
    assert "Track your courses to add classes to this summary." in text


def test_events_sort_by_local_time_then_text_and_materials_follow_timed_events():
    lessons = (
        ScheduleLessonModel(4, "10:00-10:50", "Later class"),
        ScheduleLessonModel(4, "9:00-9:50", "Earlier class"),
    )
    items = (
        activity(name="Deadline", closes=ActivityDate(datetime(2026, 10, 1, 6, tzinfo=UTC))),
        activity(name="Material", kind=ActivityKind.RESOURCE, first_seen=NOW),
    )
    text = "\n".join(format_study_week(StudyWeek(START, lessons, EdersSnapshot(items, NOW), True)))
    assert (
        text.index("Earlier class")
        < text.index("Later class")
        < text.index(">Deadline</a>")
        < text.index(">Material</a>")
    )


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_long_week_escapes_dynamic_html_and_splits_only_at_complete_lines(locale):
    lessons = tuple(
        ScheduleLessonModel(4, "9:00-9:50", f"Class-{index:03} <unsafe> & " + "x" * 250) for index in range(50)
    )
    item = activity(name="<unsafe> & material", course=EdersCourse(20, "Course <unsafe> &"), closes=ActivityDate(NOW))
    with i18n.use_locale(locale):
        chunks = format_study_week(StudyWeek(START, lessons, EdersSnapshot((item,), NOW), True))
    assert len(chunks) > 1 and all(0 < len(chunk) <= 3500 for chunk in chunks)
    text = "\n".join(chunks)
    assert "<unsafe>" not in text and "&lt;unsafe&gt; &amp;" in text
    assert 'href="https://example.com/?a=1&amp;b=2"' in text
    assert all(text.count(f"Class-{index:03}") == 1 for index in range(50))
    assert "x" * 201 not in text
    for chunk in chunks:
        assert chunk.count("<b>") == chunk.count("</b>")
        assert chunk.count("<a ") == chunk.count("</a>")


def message():
    result = AsyncMock(spec=Message)
    result.from_user = SimpleNamespace(id=42)
    result.answer = AsyncMock()
    return result


@pytest.mark.parametrize(
    "error,text,keyboard",
    [
        (UserNotFoundError(42), "Please start with the /start command", False),
        (
            UserHasNoCredentialsError(42),
            "You haven't saved your OBIS credentials. Enter them using the button below.",
            True,
        ),
        (ObisLoginError(), "Your OBIS credentials are invalid. Enter them again using the button below.", True),
        (EdersFetchError(), "Could not load eders. Try again later.", False),
        (EdersParseError(), "Could not load eders. Try again later.", False),
        (EdersUnsafeUrlError(), "Could not load eders. Try again later.", False),
        (ObisParseError(), "Could not load eders. Try again later.", False),
    ],
)
async def test_week_handler_returns_expected_errors_without_loading_message(error, text, keyboard):
    incoming, service = message(), AsyncMock()
    service.execute.side_effect = error
    await on_week_command(incoming, service)
    service.execute.assert_awaited_once_with(42)
    assert incoming.answer.await_count == 1
    response = incoming.answer.await_args_list[0]
    assert bool(response.kwargs.get("reply_markup")) is keyboard
    assert response.args == (text,)


async def test_week_handler_does_nothing_without_sender():
    incoming, service = message(), AsyncMock()
    incoming.from_user = None
    await on_week_command(incoming, service)
    incoming.answer.assert_not_awaited()
    service.execute.assert_not_awaited()


async def test_week_handler_sends_chunks_sequentially_with_previews_disabled():
    incoming, service = message(), AsyncMock()
    week = StudyWeek(
        START, tuple(ScheduleLessonModel(4, "9:00-9:50", "x" * 200) for _ in range(40)), EdersSnapshot((), NOW), True
    )
    service.execute.return_value = week
    chunks = format_study_week(week)
    await on_week_command(incoming, service)
    assert [call.args[0] for call in incoming.answer.await_args_list] == chunks
    assert all(call.kwargs["link_preview_options"].is_disabled for call in incoming.answer.await_args_list)


async def test_unexpected_week_failure_propagates():
    incoming, service = message(), AsyncMock()
    service.execute.side_effect = RuntimeError("unexpected")
    with pytest.raises(RuntimeError, match="unexpected"):
        await on_week_command(incoming, service)
    incoming.answer.assert_not_awaited()


def test_week_handler_keeps_private_command_filter():
    handler = next(item for item in router.message.handlers if item.callback.__name__ == "on_week_command")
    assert handler.flags["private_chat_only"] is True
    assert handler.filters[0].callback.commands == ("week",)


async def test_partial_telegram_failure_stops_remaining_week_chunks():
    incoming, service = message(), AsyncMock()
    week = StudyWeek(
        START,
        tuple(ScheduleLessonModel(4, "9:00-9:50", "x" * 200) for _ in range(60)),
        EdersSnapshot((), NOW),
        True,
    )
    service.execute.return_value = week
    chunks = format_study_week(week)
    assert len(chunks) > 2
    incoming.answer.side_effect = [None, None, RuntimeError("delivery failed")]
    with pytest.raises(RuntimeError, match="delivery failed"):
        await on_week_command(incoming, service)
    assert [call.args[0] for call in incoming.answer.await_args_list] == chunks[:3]
    service.execute.assert_awaited_once_with(42)


async def test_study_week_provider_owns_request_scoped_use_case():
    async with make_async_container(
        CoreProvider(),
        ObisProvider(),
        UsersProvider(),
        NotificationsProvider(),
        ScheduleProvider(),
        EdersProvider(),
        StudyWeekProvider(),
    ) as container:
        async with container() as request:
            first = await request.get(GetStudyWeek)
            assert first is await request.get(GetStudyWeek)
        async with container() as request:
            second = await request.get(GetStudyWeek)
            assert first is not second
            assert isinstance(second, GetStudyWeek)
