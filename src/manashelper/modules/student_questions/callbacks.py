from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class StudentQuestionsStep(StrEnum):
    COURSE = "course"
    SEARCH = "search"
    FOUND = "found"
    BETA = "beta"


class StudentQuestionsAnswerCallback(CallbackData, prefix="sqa"):
    session_id: str
    step: StudentQuestionsStep
    answer: str


class StudentQuestionsControlAction(StrEnum):
    RESTART = "restart"
    CANCEL = "cancel"


class StudentQuestionsControlCallback(CallbackData, prefix="sqc"):
    session_id: str
    action: StudentQuestionsControlAction
