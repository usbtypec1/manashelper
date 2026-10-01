from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from manashelper.bot.callback_data import (
    StudentQuestionsAnswerCallback,
    StudentQuestionsControlAction,
    StudentQuestionsControlCallback,
    StudentQuestionsStep,
)
from manashelper.services.student_questions import StudentCourse


def _course_label(course: StudentCourse) -> str:
    match course:
        case StudentCourse.PREPARATORY:
            return _("student_questions.preparatory")
        case StudentCourse.YEAR_1:
            return _("student_questions.year_1")
        case StudentCourse.YEAR_2:
            return _("student_questions.year_2")
        case StudentCourse.YEAR_3:
            return _("student_questions.year_3")
        case StudentCourse.YEAR_4:
            return _("student_questions.year_4")
        case StudentCourse.YEAR_5:
            return _("student_questions.year_5")
        case StudentCourse.NOT_STUDENT:
            return _("student_questions.not_student")


def _cancel_button(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("common.cancel"),
        callback_data=StudentQuestionsControlCallback(
            session_id=session_id, action=StudentQuestionsControlAction.CANCEL
        ),
    )
    return builder.as_markup()


def build_student_questions_keyboard(session_id: str, step: StudentQuestionsStep | None = None) -> InlineKeyboardMarkup:
    if step is None:
        return _cancel_button(session_id)
    builder = InlineKeyboardBuilder()
    if step is StudentQuestionsStep.COURSE:
        for course in StudentCourse:
            builder.button(
                text=_course_label(course),
                callback_data=StudentQuestionsAnswerCallback(session_id=session_id, step=step, answer=course.value),
            )
        builder.adjust(1, 3, 2, 1)
    else:
        builder.button(
            text=_("student_questions.yes"),
            callback_data=StudentQuestionsAnswerCallback(session_id=session_id, step=step, answer="yes"),
        )
        builder.button(
            text=_("student_questions.no"),
            callback_data=StudentQuestionsAnswerCallback(session_id=session_id, step=step, answer="no"),
        )
        builder.adjust(2)
    builder.attach(InlineKeyboardBuilder.from_markup(_cancel_button(session_id)))
    return builder.as_markup()


def build_student_questions_overwrite_keyboard(session_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=_("student_questions.fill_again"),
        callback_data=StudentQuestionsControlCallback(
            session_id=session_id, action=StudentQuestionsControlAction.RESTART
        ),
    )
    builder.adjust(1)
    builder.attach(InlineKeyboardBuilder.from_markup(_cancel_button(session_id)))
    return builder.as_markup()
