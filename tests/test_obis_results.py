import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.bot.callback_data import ObisResultsPageCallback
from manashelper.bot.routers.obis import (
    MAX_SAVED_RESULTS,
    RESULTS_KEY,
    on_attendance_button,
    on_exams_button,
    on_obis_results_page,
)
from manashelper.localization.i18n import i18n
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.scraping.obis_parser import ObisParseError
from manashelper.services.obis import (
    ExamModel,
    LessonAttendanceModel,
    LessonExamsModel,
    UserHasNoCredentialsError,
    UserNotFoundError,
)

USER_ID = 900_001


def _context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=USER_ID, is_bot=False, first_name="Tester"),
        chat=Chat(id=USER_ID, type="private"),
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, SendMessage):
            return Message(message_id=40 + len(_methods(request, SendMessage)), date=0, chat=message.chat).as_(bot)
        if isinstance(method, EditMessageText):
            return Message(message_id=method.message_id, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID))
    return message, state, request


def _methods(request, method_type):
    return [call.args[1] for call in request.await_args_list if isinstance(call.args[1], method_type)]


def _lessons(kind, count=5):
    if kind == "grades":
        return [
            LessonExamsModel(f"Math <b>& algebra {index}", f"MAT{index}", [ExamModel("Midterm <test>", "95")])
            for index in range(count)
        ]
    return [LessonAttendanceModel(f"Physics {index}", f"PHY{index}", 25.0, None, 0, None) for index in range(count)]


def _handler_and_fetch(service, kind):
    if kind == "grades":
        return on_exams_button, service.get_exam_grades
    return on_attendance_button, service.get_attendance


def _callback(message, message_id):
    return CallbackQuery(
        id=f"page-{message_id}",
        from_user=message.from_user,
        chat_instance="chat",
        message=Message(message_id=message_id, date=0, chat=message.chat).as_(message.bot),
    ).as_(message.bot)


@pytest.mark.parametrize("kind", ["grades", "attendance"])
async def test_loading_message_appears_before_fetch_and_is_replaced_with_compact_page(monkeypatch, kind) -> None:
    message, state, request = _context(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    started, release = asyncio.Event(), asyncio.Event()

    async def load(user_id):
        assert user_id == USER_ID
        assert len(_methods(request, SendMessage)) == 1
        started.set()
        await release.wait()
        return _lessons(kind)

    fetch.side_effect = load
    await state.update_data(student_number="existing-form-data")
    with i18n.context(), i18n.use_locale("en"):
        task = asyncio.create_task(handler(message, state, service))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            initial = _methods(request, SendMessage)[0]
            assert "Loading" in initial.text
            assert initial.parse_mode is None
            assert not _methods(request, EditMessageText)
        finally:
            release.set()
            await task
    final = _methods(request, EditMessageText)[0]
    assert final.message_id == 41
    assert final.parse_mode is None
    assert "page 1/3" in final.text.lower()
    assert "algebra 2" not in final.text and "Physics 2" not in final.text
    next_button = final.reply_markup.inline_keyboard[0][0]
    assert ObisResultsPageCallback.unpack(next_button.callback_data).page == 1
    fetch.assert_awaited_once_with(USER_ID)
    assert len(_methods(request, SendMessage)) == 1
    assert all(isinstance(call.args[1], (SendMessage, EditMessageText)) for call in request.await_args_list)
    data = await state.get_data()
    assert data["student_number"] == "existing-form-data"
    assert len(data[RESULTS_KEY]["41"]) == 3


@pytest.mark.parametrize("kind", ["grades", "attendance"])
@pytest.mark.parametrize("count", [0, 1, 2])
async def test_single_page_and_empty_results_have_no_navigation(monkeypatch, kind, count) -> None:
    message, state, request = _context(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    fetch.return_value = _lessons(kind, count)
    with i18n.context(), i18n.use_locale("ru"):
        await handler(message, state, service)
        final = _methods(request, EditMessageText)[0]
        if count == 0:
            empty_key = "obis.no_grades" if kind == "grades" else "obis.no_subjects"
            assert i18n.gettext(empty_key) in final.text
    assert final.reply_markup is None
    assert RESULTS_KEY not in await state.get_data()


@pytest.mark.parametrize("kind", ["grades", "attendance"])
@pytest.mark.parametrize(
    "error, text_key, credentials_keyboard",
    [
        (UserNotFoundError(USER_ID), "common.start_required", False),
        (UserHasNoCredentialsError(USER_ID), "obis.credentials_missing", True),
        (ObisLoginError("login failed"), "obis.credentials_invalid", True),
        (ObisParseError("parse failed"), "obis.fetch_failed", False),
        (httpx.ReadTimeout("timeout"), "obis.fetch_failed", False),
    ],
)
async def test_fetch_error_replaces_loading_message_with_actionable_error(
    monkeypatch, kind, error, text_key, credentials_keyboard
) -> None:
    message, state, request = _context(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    fetch.side_effect = error
    with i18n.context(), i18n.use_locale("en"):
        await handler(message, state, service)
        final = _methods(request, EditMessageText)[0]
        assert final.text == i18n.gettext(text_key)
    assert final.message_id == 41
    assert (final.reply_markup is not None) is credentials_keyboard
    assert len(_methods(request, SendMessage)) == 1
    assert RESULTS_KEY not in await state.get_data()


async def test_pages_are_bound_to_each_message_and_do_not_refetch_obis(monkeypatch) -> None:
    message, state, request = _context(monkeypatch)
    service = AsyncMock()
    service.get_exam_grades.return_value = _lessons("grades")
    service.get_attendance.return_value = _lessons("attendance")
    with i18n.context(), i18n.use_locale("en"):
        await on_exams_button(message, state, service)
        await on_attendance_button(message, state, service)
        await on_obis_results_page(_callback(message, 41), ObisResultsPageCallback(page=1), state)
        await on_obis_results_page(_callback(message, 42), ObisResultsPageCallback(page=2), state)
    edits = _methods(request, EditMessageText)
    grades, attendance = edits[-2:]
    assert grades.message_id == 41
    assert "Math <b>& algebra 2" in grades.text
    assert "Physics" not in grades.text
    assert grades.parse_mode is None
    assert len(grades.reply_markup.inline_keyboard[0]) == 2
    assert attendance.message_id == 42
    assert "Physics 4" in attendance.text
    assert "algebra" not in attendance.text
    assert len(attendance.reply_markup.inline_keyboard[0]) == 1
    assert ObisResultsPageCallback.unpack(attendance.reply_markup.inline_keyboard[0][0].callback_data).page == 1
    service.get_exam_grades.assert_awaited_once_with(USER_ID)
    service.get_attendance.assert_awaited_once_with(USER_ID)
    assert len(_methods(request, AnswerCallbackQuery)) == 2


@pytest.mark.parametrize("page", [-1, 2, 100])
async def test_missing_or_out_of_range_page_answers_without_editing(monkeypatch, page) -> None:
    message, state, request = _context(monkeypatch)
    await state.update_data({RESULTS_KEY: {"41": ["First", "Second"]}})
    with i18n.context(), i18n.use_locale("en"):
        await on_obis_results_page(_callback(message, 41), ObisResultsPageCallback(page=page), state)
        await on_obis_results_page(_callback(message, 99), ObisResultsPageCallback(page=0), state)
    assert not _methods(request, EditMessageText)
    assert all(answer.show_alert for answer in _methods(request, AnswerCallbackQuery))


async def test_saved_results_are_bounded_and_keep_latest_messages(monkeypatch) -> None:
    message, state, request = _context(monkeypatch)
    service = AsyncMock()
    service.get_exam_grades.return_value = _lessons("grades")
    with i18n.context(), i18n.use_locale("en"):
        for _ in range(MAX_SAVED_RESULTS + 1):
            await on_exams_button(message, state, service)
    snapshots = (await state.get_data())[RESULTS_KEY]
    assert len(snapshots) == MAX_SAVED_RESULTS
    assert "41" not in snapshots
    assert str(40 + MAX_SAVED_RESULTS + 1) in snapshots


async def test_repeated_page_callback_still_answers_when_message_is_not_modified(monkeypatch) -> None:
    message, state, request = _context(monkeypatch)
    await state.update_data({RESULTS_KEY: {"41": ["First", "Second"]}})
    respond = request.side_effect

    async def unchanged(bot, method, **kwargs):
        if isinstance(method, EditMessageText):
            raise TelegramBadRequest(method=method, message="message is not modified")
        return await respond(bot, method, **kwargs)

    request.side_effect = unchanged
    with i18n.context(), i18n.use_locale("en"):
        await on_obis_results_page(_callback(message, 41), ObisResultsPageCallback(page=0), state)
    answer = _methods(request, AnswerCallbackQuery)[0]
    assert not answer.show_alert


async def test_request_cancellation_cancels_obis_fetch(monkeypatch) -> None:
    message, state, request = _context(monkeypatch)
    started, cancelled = asyncio.Event(), asyncio.Event()
    service = AsyncMock()

    async def load(user_id):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    service.get_exam_grades.side_effect = load
    with i18n.context(), i18n.use_locale("en"):
        task = asyncio.create_task(on_exams_button(message, state, service))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set()
    assert not _methods(request, EditMessageText)
