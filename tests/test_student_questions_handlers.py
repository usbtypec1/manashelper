from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from manashelper.bot.callback_data import (
    StudentQuestionsAnswerCallback,
    StudentQuestionsControlAction,
    StudentQuestionsControlCallback,
    StudentQuestionsStep,
)
from manashelper.bot.keyboards.student_questions import build_student_questions_keyboard
from manashelper.bot.routers.student_questions import (
    SESSION_KEY,
    StudentQuestionsForm,
    on_student_questions_answer,
    on_student_questions_control,
    on_student_questions_start,
    on_student_questions_text,
    router,
)
from manashelper.localization.i18n import i18n
from manashelper.services.student_questions import AlreadySubmittedError, StudentCourse

USER_ID = 990_001


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    message = Message(
        message_id=1,
        date=0,
        from_user=User(id=USER_ID, is_bot=False, first_name="Tester"),
        chat=Chat(id=USER_ID, type="private"),
        text="/start student_questions",
    ).as_(bot)

    async def respond(_bot, method, **kwargs):
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(message_id=42, date=0, chat=message.chat).as_(bot)
        return True

    request = AsyncMock(side_effect=respond)
    monkeypatch.setattr(bot.session, "make_request", request)
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID))
    service = AsyncMock()
    service.has_submitted.return_value = False
    with i18n.context(), i18n.use_locale("en"):
        yield message, state, request, service


def _methods(request, kind):
    return [call.args[1] for call in request.await_args_list if isinstance(call.args[1], kind)]


def _callback(message):
    return CallbackQuery(
        id="answer",
        from_user=message.from_user,
        chat_instance="chat",
        message=Message(message_id=42, date=0, chat=message.chat).as_(message.bot),
    ).as_(message.bot)


async def _answer(context, step, answer, session_id=None):
    message, state, _, service = context
    session_id = session_id or (await state.get_data())[SESSION_KEY]
    await on_student_questions_answer(
        _callback(message),
        StudentQuestionsAnswerCallback(session_id=session_id, step=step, answer=answer),
        state,
        service,
    )


async def _text(context, text):
    message, state, _, _ = context
    await on_student_questions_text(message.model_copy(update={"text": text}), state)


@pytest.mark.parametrize(
    ("had_questions", "found_answers", "beta"), [(False, None, False), (True, False, True), (True, True, True)]
)
async def test_survey_branches_and_final_submission(context, had_questions, found_answers, beta) -> None:
    message, state, request, service = context
    await on_student_questions_start(message, state, service)
    assert await state.get_state() == StudentQuestionsForm.course.state
    await _answer(context, StudentQuestionsStep.COURSE, StudentCourse.PREPARATORY.value)
    assert await state.get_state() == StudentQuestionsForm.search.state
    await _answer(context, StudentQuestionsStep.SEARCH, "yes" if had_questions else "no")
    if had_questions:
        assert await state.get_state() == StudentQuestionsForm.questions.state
        await _text(context, "Where can I find scholarships?")
        assert await state.get_state() == StudentQuestionsForm.found.state
        await _answer(context, StudentQuestionsStep.FOUND, "yes" if found_answers else "no")
        if found_answers:
            assert await state.get_state() == StudentQuestionsForm.sources.state
            await _text(context, "Admissions office")
    assert await state.get_state() == StudentQuestionsForm.beta.state
    service.submit.assert_not_awaited()
    await _answer(context, StudentQuestionsStep.BETA, "yes" if beta else "no")
    args = service.submit.await_args
    assert args.args[0] == USER_ID and args.kwargs == {"overwrite": False}
    answers = args.args[1]
    assert answers.course is StudentCourse.PREPARATORY and answers.had_questions is had_questions
    assert answers.questions == ("Where can I find scholarships?" if had_questions else None)
    assert answers.found_answers is found_answers
    assert answers.answer_sources == ("Admissions office" if found_answers else None)
    assert answers.wants_beta is beta
    final = _methods(request, SendMessage)[-1]
    assert "Thank you" in final.text
    assert ("within a month" in final.text) is beta
    assert final.reply_markup.keyboard
    assert await state.get_state() is None and await state.get_data() == {}


async def test_existing_response_requires_confirmation_and_explicit_overwrite(context) -> None:
    message, state, request, service = context
    service.has_submitted.return_value = True
    await on_student_questions_start(message, state, service)
    assert await state.get_state() == StudentQuestionsForm.overwrite.state
    warning = _methods(request, SendMessage)[-1]
    assert "already completed" in warning.text and "replace" in warning.text
    restart = StudentQuestionsControlCallback.unpack(warning.reply_markup.inline_keyboard[0][0].callback_data)
    assert restart.action is StudentQuestionsControlAction.RESTART
    service.submit.assert_not_awaited()
    await on_student_questions_control(_callback(message), restart, state)
    await _answer(context, StudentQuestionsStep.COURSE, "5")
    await _answer(context, StudentQuestionsStep.SEARCH, "no")
    service.submit.assert_not_awaited()
    await _answer(context, StudentQuestionsStep.BETA, "no")
    assert service.submit.await_args.kwargs == {"overwrite": True}


async def test_cancel_does_not_modify_saved_response(context) -> None:
    message, state, _, service = context
    service.has_submitted.return_value = True
    await on_student_questions_start(message, state, service)
    data = await state.get_data()
    await on_student_questions_control(
        _callback(message),
        StudentQuestionsControlCallback(session_id=data[SESSION_KEY], action=StudentQuestionsControlAction.CANCEL),
        state,
    )
    assert await state.get_state() is None
    service.submit.assert_not_awaited()


async def test_stale_buttons_and_duplicate_step_do_not_change_new_survey(context) -> None:
    message, state, request, service = context
    await on_student_questions_start(message, state, service)
    old_session = (await state.get_data())[SESSION_KEY]
    await on_student_questions_start(message, state, service)
    new_session = (await state.get_data())[SESSION_KEY]
    assert new_session != old_session
    await _answer(context, StudentQuestionsStep.COURSE, "1", old_session)
    assert await state.get_state() == StudentQuestionsForm.course.state
    assert _methods(request, AnswerCallbackQuery)[-1].show_alert
    await _answer(context, StudentQuestionsStep.COURSE, "2")
    await _answer(context, StudentQuestionsStep.COURSE, "3")
    assert (await state.get_data())["course"] == "2"
    assert await state.get_state() == StudentQuestionsForm.search.state
    service.submit.assert_not_awaited()


async def test_invalid_text_stays_on_question_and_does_not_submit(context) -> None:
    message, state, request, service = context
    await on_student_questions_start(message, state, service)
    await _answer(context, StudentQuestionsStep.COURSE, "1")
    await _answer(context, StudentQuestionsStep.SEARCH, "yes")
    for text in (None, " ", "x" * 4001):
        await _text(context, text)
        assert await state.get_state() == StudentQuestionsForm.questions.state
        assert "4000" in _methods(request, SendMessage)[-1].text
    service.submit.assert_not_awaited()


async def test_duplicate_submission_race_requests_confirmation_instead_of_overwriting(context) -> None:
    message, state, request, service = context
    await on_student_questions_start(message, state, service)
    await _answer(context, StudentQuestionsStep.COURSE, "1")
    await _answer(context, StudentQuestionsStep.SEARCH, "no")
    service.submit.side_effect = AlreadySubmittedError
    await _answer(context, StudentQuestionsStep.BETA, "yes")
    assert await state.get_state() == StudentQuestionsForm.overwrite.state
    assert "already completed" in _methods(request, SendMessage)[-1].text
    assert service.submit.await_args.kwargs == {"overwrite": False}


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_all_course_options_are_localized_and_callbacks_fit_telegram_limit(locale) -> None:
    with i18n.context(), i18n.use_locale(locale):
        keyboard = build_student_questions_keyboard("a" * 32, StudentQuestionsStep.COURSE)
        buttons = [button for row in keyboard.inline_keyboard for button in row]
        assert len(buttons) == 8
        assert [StudentQuestionsAnswerCallback.unpack(button.callback_data).answer for button in buttons[:-1]] == list(
            StudentCourse
        )
        assert all("student_questions." not in button.text for button in buttons)
        assert all(len(button.callback_data.encode()) <= 64 for button in buttons)


async def test_deep_link_filter_claims_only_survey_and_dispatches_before_generic_start(context) -> None:
    message, state, request, service = context
    survey_filter = router.message.handlers[0].filters[0].callback
    dispatcher = Dispatcher(storage=state.storage)
    dispatcher.message.register(on_student_questions_start, survey_filter)
    generic_start = AsyncMock()

    async def fallback(message):
        await generic_start(message)

    dispatcher.message.register(fallback, CommandStart())
    await dispatcher.feed_update(message.bot, Update(update_id=1, message=message), student_questions_service=service)
    service.has_submitted.assert_awaited_once_with(USER_ID)
    generic_start.assert_not_awaited()
    assert "What year" in _methods(request, SendMessage)[-1].text
    for payload in ("ad_123", "market", "", "student_questions_extra"):
        other = message.model_copy(update={"text": f"/start {payload}".strip()})
        assert not await survey_filter(other, message.bot)
