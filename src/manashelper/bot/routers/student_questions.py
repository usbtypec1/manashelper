import uuid

from aiogram import F, Router, flags
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.utils.i18n import gettext as _
from dishka import FromDishka

from manashelper.bot.callback_data import (
    StudentQuestionsAnswerCallback,
    StudentQuestionsControlAction,
    StudentQuestionsControlCallback,
    StudentQuestionsStep,
)
from manashelper.bot.keyboards.student_questions import (
    build_student_questions_keyboard,
    build_student_questions_overwrite_keyboard,
)
from manashelper.bot.routers.start import build_main_keyboard
from manashelper.services.student_questions import (
    ANSWER_MAX_LENGTH,
    AlreadySubmittedError,
    StudentCourse,
    StudentQuestionsAnswers,
    StudentQuestionsService,
    validate_text_answer,
)

router = Router(name="student_questions")
SESSION_KEY = "student_questions_session"


class StudentQuestionsForm(StatesGroup):
    overwrite = State()
    course = State()
    search = State()
    questions = State()
    found = State()
    sources = State()
    beta = State()


_STEP_STATES = {
    StudentQuestionsStep.COURSE: StudentQuestionsForm.course,
    StudentQuestionsStep.SEARCH: StudentQuestionsForm.search,
    StudentQuestionsStep.FOUND: StudentQuestionsForm.found,
    StudentQuestionsStep.BETA: StudentQuestionsForm.beta,
}


async def _show_question(
    message: Message,
    state: FSMContext,
    form_state: State,
    text: str,
    *,
    step: StudentQuestionsStep | None = None,
    edit: bool = False,
) -> None:
    await state.set_state(form_state)
    session_id: str = (await state.get_data())[SESSION_KEY]
    send = message.edit_text if edit else message.answer
    await send(text, reply_markup=build_student_questions_keyboard(session_id, step))


async def _begin(message: Message, state: FSMContext, *, overwrite: bool = False) -> None:
    await state.clear()
    await state.update_data({SESSION_KEY: uuid.uuid4().hex, "overwrite": overwrite})
    await message.answer(_("student_questions.intro"), reply_markup=ReplyKeyboardRemove())
    await _show_question(
        message,
        state,
        StudentQuestionsForm.course,
        _("student_questions.course_prompt"),
        step=StudentQuestionsStep.COURSE,
    )


async def _warn_completed(message: Message, state: FSMContext) -> None:
    await state.clear()
    session_id = uuid.uuid4().hex
    await state.update_data({SESSION_KEY: session_id})
    await state.set_state(StudentQuestionsForm.overwrite)
    await message.answer(
        _("student_questions.already_completed"), reply_markup=build_student_questions_overwrite_keyboard(session_id)
    )


@router.message(CommandStart(deep_link=True, magic=F.args == "student_questions"))
@flags.private_chat_only
async def on_student_questions_start(
    message: Message, state: FSMContext, student_questions_service: FromDishka[StudentQuestionsService]
) -> None:
    if message.from_user is None:
        return
    if await student_questions_service.has_submitted(message.from_user.id):
        await _warn_completed(message, state)
        return
    await _begin(message, state)


@router.callback_query(StudentQuestionsControlCallback.filter())
@flags.private_chat_only
async def on_student_questions_control(
    callback_query: CallbackQuery, callback_data: StudentQuestionsControlCallback, state: FSMContext
) -> None:
    data = await state.get_data()
    current = await state.get_state()
    message = callback_query.message
    if (
        not isinstance(message, Message)
        or data.get(SESSION_KEY) != callback_data.session_id
        or current is None
        or not current.startswith("StudentQuestionsForm:")
    ):
        await callback_query.answer(_("student_questions.expired"), show_alert=True)
        return
    if callback_data.action is StudentQuestionsControlAction.CANCEL:
        await message.edit_reply_markup(reply_markup=None)
        await message.answer(_("student_questions.cancelled"), reply_markup=build_main_keyboard())
        await state.clear()
    elif current == StudentQuestionsForm.overwrite.state:
        await message.edit_reply_markup(reply_markup=None)
        await _begin(message, state, overwrite=True)
    else:
        await callback_query.answer(_("student_questions.expired"), show_alert=True)
        return
    await callback_query.answer()


@router.callback_query(StudentQuestionsAnswerCallback.filter())
@flags.private_chat_only
async def on_student_questions_answer(
    callback_query: CallbackQuery,
    callback_data: StudentQuestionsAnswerCallback,
    state: FSMContext,
    student_questions_service: FromDishka[StudentQuestionsService],
) -> None:
    data = await state.get_data()
    message = callback_query.message
    if (
        not isinstance(message, Message)
        or data.get(SESSION_KEY) != callback_data.session_id
        or await state.get_state() != _STEP_STATES[callback_data.step].state
    ):
        await callback_query.answer(_("student_questions.expired"), show_alert=True)
        return
    if callback_data.step is StudentQuestionsStep.COURSE:
        try:
            course = StudentCourse(callback_data.answer)
        except ValueError:
            await callback_query.answer(_("student_questions.use_buttons"), show_alert=True)
            return
        await state.update_data(course=course.value)
        await _show_question(
            message,
            state,
            StudentQuestionsForm.search,
            _("student_questions.search_prompt"),
            step=StudentQuestionsStep.SEARCH,
            edit=True,
        )
    else:
        if callback_data.answer not in ("yes", "no"):
            await callback_query.answer(_("student_questions.use_buttons"), show_alert=True)
            return
        yes = callback_data.answer == "yes"
        if callback_data.step is StudentQuestionsStep.SEARCH:
            await state.update_data(had_questions=yes)
            if yes:
                await _show_question(
                    message, state, StudentQuestionsForm.questions, _("student_questions.questions_prompt"), edit=True
                )
            else:
                await _show_question(
                    message,
                    state,
                    StudentQuestionsForm.beta,
                    _("student_questions.beta_prompt"),
                    step=StudentQuestionsStep.BETA,
                    edit=True,
                )
        elif callback_data.step is StudentQuestionsStep.FOUND:
            await state.update_data(found_answers=yes)
            if yes:
                await _show_question(
                    message, state, StudentQuestionsForm.sources, _("student_questions.sources_prompt"), edit=True
                )
            else:
                await _show_question(
                    message,
                    state,
                    StudentQuestionsForm.beta,
                    _("student_questions.beta_prompt"),
                    step=StudentQuestionsStep.BETA,
                    edit=True,
                )
        else:
            answers = StudentQuestionsAnswers(
                course=StudentCourse(data["course"]),
                had_questions=data["had_questions"],
                questions=data.get("questions"),
                found_answers=data.get("found_answers"),
                answer_sources=data.get("answer_sources"),
                wants_beta=yes,
            )
            try:
                await student_questions_service.submit(
                    callback_query.from_user.id, answers, overwrite=data.get("overwrite", False)
                )
            except AlreadySubmittedError:
                await _warn_completed(message, state)
                await callback_query.answer()
                return
            await message.edit_reply_markup(reply_markup=None)
            text = _("student_questions.thanks")
            if yes:
                text += "\n\n" + _("student_questions.beta_follow_up")
            await message.answer(text, reply_markup=build_main_keyboard())
            await state.clear()
    await callback_query.answer()


@router.message(StateFilter(StudentQuestionsForm.questions, StudentQuestionsForm.sources), ~F.text.startswith("/"))
@flags.private_chat_only
async def on_student_questions_text(message: Message, state: FSMContext) -> None:
    try:
        answer = validate_text_answer(message.text)
    except ValueError:
        await message.answer(_("student_questions.invalid_text").format(max=ANSWER_MAX_LENGTH))
        return
    if await state.get_state() == StudentQuestionsForm.questions.state:
        await state.update_data(questions=answer)
        await _show_question(
            message,
            state,
            StudentQuestionsForm.found,
            _("student_questions.found_prompt"),
            step=StudentQuestionsStep.FOUND,
        )
    else:
        await state.update_data(answer_sources=answer)
        await _show_question(
            message,
            state,
            StudentQuestionsForm.beta,
            _("student_questions.beta_prompt"),
            step=StudentQuestionsStep.BETA,
        )


@router.message(
    StateFilter(
        StudentQuestionsForm.overwrite,
        StudentQuestionsForm.course,
        StudentQuestionsForm.search,
        StudentQuestionsForm.found,
        StudentQuestionsForm.beta,
    ),
    ~F.text.startswith("/"),
)
@flags.private_chat_only
async def on_student_questions_button_required(message: Message) -> None:
    await message.answer(_("student_questions.use_buttons"))
