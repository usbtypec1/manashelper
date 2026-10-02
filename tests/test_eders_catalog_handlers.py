from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User

from manashelper.bot.callback_data import EdersCatalogCallback
from manashelper.bot.routers.eders_catalog import (
    CATALOG_KEY,
    MAX_CATALOGS,
    on_eders_catalog_command,
    on_eders_catalog_page,
)
from manashelper.localization.i18n import i18n
from manashelper.scraping.eders_client import EdersFetchError
from manashelper.scraping.obis_client import ObisLoginError
from manashelper.services.eders_models import (
    ActivityKind,
    EdersActivity,
    EdersCatalogView,
    EdersCourse,
    EdersGrade,
    EdersSnapshot,
)
from manashelper.services.obis import UserHasNoCredentialsError

USER_ID = 990_001


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=USER_ID, is_bot=False, first_name="Tester"),
        chat=Chat(id=USER_ID, type="private"),
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID))
    courses = tuple(EdersCourse(index, f"Course {index:02}") for index in range(1, 13))
    materials = tuple(
        EdersActivity(
            index,
            courses[0],
            ActivityKind.RESOURCE,
            f"Reading {index}",
            f"https://eders.manas.edu.kg/mod/resource/view.php?id={index}",
            section="Week 1",
        )
        for index in range(1, 4)
    )
    grade = EdersGrade(
        301, courses[0], "Work", "https://eders.manas.edu.kg/mod/assign/view.php?id=20", grade="0", feedback="<comment>"
    )
    snapshot = EdersSnapshot(materials, datetime.now(UTC), (grade,), True, True, courses)
    service = AsyncMock()
    service.get_snapshot.return_value = snapshot
    with i18n.context(), i18n.use_locale("en"):
        yield message, state, request, service


def methods(request, kind):
    return [call.args[1] for call in request.await_args_list if isinstance(call.args[1], kind)]


async def click(context, data, message_text=None, markup=None):
    message, state, _, _ = context
    callback = CallbackQuery(
        id="catalog",
        from_user=message.from_user,
        chat_instance="chat",
        message=Message(message_id=42, date=0, chat=message.chat, text=message_text, reply_markup=markup).as_(
            message.bot
        ),
    ).as_(message.bot)
    await on_eders_catalog_page(callback, data, state)


async def test_material_course_pagination_and_search_use_one_fetch_and_keep_user_state(context):
    message, state, request, service = context
    await state.update_data(other_feature="keep")
    await on_eders_catalog_command(message, CommandObject(command="materials"), state, service)
    assert len(methods(request, SendMessage)) == 1
    first = methods(request, EditMessageText)[-1]
    buttons = [b for row in first.reply_markup.inline_keyboard for b in row]
    assert len(buttons) == 7 and buttons[0].text == "Course 01"
    next_page = EdersCatalogCallback.unpack(buttons[-1].callback_data)
    assert next_page.page == 1
    await click(context, next_page)
    second = methods(request, EditMessageText)[-1]
    assert second.reply_markup.inline_keyboard[0][0].text == "Course 06"
    pick_course = EdersCatalogCallback.unpack(first.reply_markup.inline_keyboard[0][0].callback_data)
    await click(context, pick_course)
    page = methods(request, EditMessageText)[-1]
    assert "Reading 1" in page.text and "Week 1" in page.text and "Last updated" in page.text
    await click(context, pick_course.model_copy(update={"page": 999}))
    assert "Reading 3" in methods(request, EditMessageText)[-1].text
    service.get_snapshot.assert_awaited_once_with(USER_ID)
    assert (await state.get_data())["other_feature"] == "keep"
    assert all(len(b.callback_data.encode()) <= 64 for b in buttons)


async def test_search_by_title_and_topic_and_separate_query_results(context):
    message, state, request, service = context
    await on_eders_catalog_command(message, CommandObject(command="materials", args="Reading 2"), state, service)
    first = methods(request, EditMessageText)[-1]
    assert "Reading 2" in first.text and "Reading 1" not in first.text
    courses_button = EdersCatalogCallback.unpack(first.reply_markup.inline_keyboard[0][0].callback_data)
    await on_eders_catalog_command(message, CommandObject(command="materials", args="no matches"), state, service)
    assert "No matching items" in methods(request, EditMessageText)[-1].text
    await click(context, courses_button.model_copy(update={"view": EdersCatalogView.MATERIALS}))
    assert "Reading 2" in methods(request, EditMessageText)[-1].text
    assert len((await state.get_data())[CATALOG_KEY]) == 2


async def test_grade_journal_shows_source_zero_feedback_and_timestamp(context):
    message, _, request, service = context
    await on_eders_catalog_command(message, CommandObject(command="eders_grades"), context[1], service)
    first = methods(request, EditMessageText)[-1]
    selected = EdersCatalogCallback.unpack(first.reply_markup.inline_keyboard[0][0].callback_data)
    await click(context, selected)
    text = methods(request, EditMessageText)[-1].text
    assert "Grade: 0" in text and "&lt;comment&gt;" in text
    assert "Source: eders" in text and "OBIS" in text and "Last updated" in text
    service.get_snapshot.assert_awaited_once()


async def test_expired_and_evicted_panels_are_rejected_without_fetch(context):
    message, state, request, service = context
    await on_eders_catalog_command(message, CommandObject(command="materials"), state, service)
    first = methods(request, EditMessageText)[-1]
    old_button = EdersCatalogCallback.unpack(first.reply_markup.inline_keyboard[0][0].callback_data)
    for _ in range(MAX_CATALOGS):
        await on_eders_catalog_command(message, CommandObject(command="materials"), state, service)
    assert len((await state.get_data())[CATALOG_KEY]) == MAX_CATALOGS
    await click(context, old_button)
    assert methods(request, AnswerCallbackQuery)[-1].show_alert
    latest = EdersCatalogCallback.unpack(
        methods(request, EditMessageText)[-1].reply_markup.inline_keyboard[0][0].callback_data
    )
    data = await state.get_data()
    session = data[CATALOG_KEY][latest.session_id]
    data[CATALOG_KEY][latest.session_id] = replace(
        session, snapshot=replace(session.snapshot, fetched_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await state.set_data(data)
    count = service.get_snapshot.await_count
    await click(context, latest)
    assert methods(request, AnswerCallbackQuery)[-1].show_alert
    assert service.get_snapshot.await_count == count


@pytest.mark.parametrize(
    "error", [UserHasNoCredentialsError(USER_ID), ObisLoginError("invalid"), EdersFetchError("failed")]
)
async def test_catalog_fetch_errors_replace_loading_and_do_not_create_panel(context, error):
    message, state, request, service = context
    service.get_snapshot.side_effect = error
    await on_eders_catalog_command(message, CommandObject(command="materials"), state, service)
    assert len(methods(request, SendMessage)) == 1 and len(methods(request, EditMessageText)) == 1
    assert not (await state.get_data()).get(CATALOG_KEY)


async def test_search_length_limit_skips_network_fetch(context):
    message, state, request, service = context
    await on_eders_catalog_command(message, CommandObject(command="materials", args="x" * 101), state, service)
    service.get_snapshot.assert_not_awaited()
    assert "100" in methods(request, SendMessage)[-1].text


async def test_full_teacher_comment_is_paginated_without_losing_text(context):
    message, state, request, service = context
    data = service.get_snapshot.return_value
    feedback = "A" * 350 + "<last part>"
    service.get_snapshot.return_value = replace(data, grades=(replace(data.grades[0], feedback=feedback),))
    await on_eders_catalog_command(message, CommandObject(command="eders_grades"), state, service)
    course = EdersCatalogCallback.unpack(
        methods(request, EditMessageText)[-1].reply_markup.inline_keyboard[0][0].callback_data
    )
    await click(context, course)
    first = methods(request, EditMessageText)[-1]
    full = EdersCatalogCallback.unpack(first.reply_markup.inline_keyboard[0][0].callback_data)
    assert full.view == EdersCatalogView.FEEDBACK
    await click(context, full)
    first_comment = methods(request, EditMessageText)[-1]
    assert "A" * 350 in first_comment.text and "last part" not in first_comment.text
    next_page = EdersCatalogCallback.unpack(first_comment.reply_markup.inline_keyboard[-1][-1].callback_data)
    assert next_page.grade_id == data.grades[0].id
    await click(context, next_page)
    second = methods(request, EditMessageText)[-1]
    assert "&lt;last part&gt;" in second.text
    back = EdersCatalogCallback.unpack(second.reply_markup.inline_keyboard[0][0].callback_data)
    await click(context, back)
    assert "Grade: 0" in methods(request, EditMessageText)[-1].text
    service.get_snapshot.assert_awaited_once()


async def test_unavailable_grade_report_shows_notice_and_keeps_materials_available(context):
    message, state, request, service = context
    service.get_snapshot.return_value = replace(service.get_snapshot.return_value, unavailable_grade_courses=(1,))
    await on_eders_catalog_command(message, CommandObject(command="eders_grades"), state, service)
    course = EdersCatalogCallback.unpack(
        methods(request, EditMessageText)[-1].reply_markup.inline_keyboard[0][0].callback_data
    )
    await click(context, course)
    text = methods(request, EditMessageText)[-1].text
    assert "hidden or unavailable" in text and "Grade: 0" not in text
    await on_eders_catalog_command(message, CommandObject(command="materials", args="Reading"), state, service)
    assert "Reading 1" in methods(request, EditMessageText)[-1].text
