import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import EditMessageText, SendMessage, SendRichMessage, SendRichMessageDraft
from aiogram.types import Chat, Message, User

from manashelper.bot import message_stream
from manashelper.bot.routers.obis import on_attendance_button, on_exams_button
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


def _message(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=USER_ID, is_bot=False, first_name="Tester"),
        chat=Chat(id=USER_ID, type="private"),
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, (SendRichMessage, SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    return message, request


def _methods(request, method_type):
    return [call.args[1] for call in request.await_args_list if isinstance(call.args[1], method_type)]


def _lessons(kind):
    if kind == "grades":
        return [
            LessonExamsModel("Math <b>& algebra", "MAT101", [ExamModel("Midterm <test>", "95")]),
            LessonExamsModel("Physics", "PHY101", [ExamModel("Final", None)]),
        ]
    return [
        LessonAttendanceModel("Math <b>& algebra", "MAT101", 25.0, None, 0, None),
        LessonAttendanceModel("Physics", "PHY101", 12.5, 12.5, 2, 1),
    ]


def _handler_and_fetch(service, kind):
    if kind == "grades":
        return on_exams_button, service.get_exam_grades
    return on_attendance_button, service.get_attendance


@pytest.mark.parametrize("kind", ["grades", "attendance"])
async def test_heading_is_visible_before_fetch_and_lessons_stream_before_persisting(monkeypatch, kind) -> None:
    message, request = _message(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    started, release = asyncio.Event(), asyncio.Event()

    async def load(user_id):
        assert user_id == USER_ID
        assert len(_methods(request, SendRichMessageDraft)) == 1
        started.set()
        await release.wait()
        return _lessons(kind)

    fetch.side_effect = load
    with i18n.context(), i18n.use_locale("en"):
        task = asyncio.create_task(handler(message, service))
        await asyncio.wait_for(started.wait(), timeout=1)
        initial = _methods(request, SendRichMessageDraft)[0]
        assert len(initial.rich_message.blocks) == 1
        assert initial.rich_message.blocks[0].type == "heading"
        assert not _methods(request, SendRichMessage)
        release.set()
        await task
    drafts = _methods(request, SendRichMessageDraft)
    assert [len(draft.rich_message.blocks) for draft in drafts] == [1, 3, 5]
    assert len({draft.draft_id for draft in drafts}) == 1
    assert drafts[0].draft_id != 0
    final = _methods(request, SendRichMessage)[0]
    assert final.rich_message == drafts[-1].rich_message
    assert final.rich_message.skip_entity_detection is True
    assert "Math <b>& algebra" in final.rich_message.blocks[1].text
    fetch.assert_awaited_once_with(USER_ID)


@pytest.mark.parametrize("kind, empty_key", [("grades", "obis.no_grades"), ("attendance", "obis.no_subjects")])
async def test_empty_result_finishes_the_preview(monkeypatch, kind, empty_key) -> None:
    message, request = _message(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    fetch.return_value = []
    with i18n.context(), i18n.use_locale("ru"):
        await handler(message, service)
        final = _methods(request, SendRichMessage)[0]
        assert final.rich_message.blocks[1].text == i18n.gettext(empty_key)
    assert len(final.rich_message.blocks) == 2


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
async def test_fetch_error_replaces_preview_with_actionable_message(
    monkeypatch, kind, error, text_key, credentials_keyboard
) -> None:
    message, request = _message(monkeypatch)
    service = AsyncMock()
    handler, fetch = _handler_and_fetch(service, kind)
    fetch.side_effect = error
    with i18n.context(), i18n.use_locale("en"):
        await handler(message, service)
        final = _methods(request, SendMessage)[0]
        assert final.text == i18n.gettext(text_key)
    assert (final.reply_markup is not None) is credentials_keyboard
    assert len(_methods(request, SendRichMessageDraft)) == 1
    assert not _methods(request, SendRichMessage)


async def test_unavailable_drafts_fall_back_to_heading_then_edit_one_message(monkeypatch) -> None:
    message, request = _message(monkeypatch)
    respond = request.side_effect

    async def without_drafts(bot, method, **kwargs):
        if isinstance(method, SendRichMessageDraft):
            raise TelegramBadRequest(method=method, message="drafts unavailable")
        return await respond(bot, method, **kwargs)

    request.side_effect = without_drafts
    service = AsyncMock()
    service.get_exam_grades.return_value = _lessons("grades")
    with i18n.context(), i18n.use_locale("en"):
        await on_exams_button(message, service)
    assert len(_methods(request, SendRichMessageDraft)) == 1
    initial = _methods(request, SendRichMessage)[0]
    assert len(initial.rich_message.blocks) == 1
    edited = _methods(request, EditMessageText)[0]
    assert edited.message_id == 42
    assert len(edited.rich_message.blocks) == 5


async def test_slow_fetch_refreshes_preview_with_same_draft_id(monkeypatch) -> None:
    message, request = _message(monkeypatch)
    monkeypatch.setattr(message_stream, "_PREVIEW_REFRESH_SECONDS", 0.01)
    refreshed = asyncio.Event()
    release = asyncio.Event()
    respond = request.side_effect

    async def capture_refresh(bot, method, **kwargs):
        if isinstance(method, SendRichMessageDraft) and len(_methods(request, SendRichMessageDraft)) >= 2:
            refreshed.set()
        return await respond(bot, method, **kwargs)

    request.side_effect = capture_refresh
    service = AsyncMock()

    async def load(user_id):
        await release.wait()
        return []

    service.get_exam_grades.side_effect = load
    with i18n.context(), i18n.use_locale("en"):
        task = asyncio.create_task(on_exams_button(message, service))
        await asyncio.wait_for(refreshed.wait(), timeout=1)
        release.set()
        await task
    drafts = _methods(request, SendRichMessageDraft)
    assert drafts[0].rich_message == drafts[1].rich_message
    assert drafts[0].draft_id == drafts[1].draft_id
    assert len(_methods(request, SendRichMessage)) == 1


async def test_cancelled_request_cancels_obis_fetch(monkeypatch) -> None:
    message, request = _message(monkeypatch)
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
        task = asyncio.create_task(on_exams_button(message, service))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set()
    assert not _methods(request, SendRichMessage)
