from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from manashelper.db.models import StudentQuestionsResponse
from manashelper.repositories.student_questions_repository import StudentQuestionsRepository

ANSWER_MAX_LENGTH = 4000


class StudentCourse(StrEnum):
    PREPARATORY = "preparatory"
    YEAR_1 = "1"
    YEAR_2 = "2"
    YEAR_3 = "3"
    YEAR_4 = "4"
    YEAR_5 = "5"
    NOT_STUDENT = "not_student"


class AlreadySubmittedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StudentQuestionsAnswers:
    course: StudentCourse
    had_questions: bool
    questions: str | None
    found_answers: bool | None
    answer_sources: str | None
    wants_beta: bool


def validate_text_answer(text: str | None) -> str:
    answer = (text or "").strip()
    if not answer or len(answer) > ANSWER_MAX_LENGTH:
        raise ValueError("Invalid survey text answer")
    return answer


class StudentQuestionsService:
    def __init__(self, student_questions_repository: StudentQuestionsRepository) -> None:
        self._repository = student_questions_repository

    async def has_submitted(self, user_id: int) -> bool:
        return await self._repository.has_response(user_id)

    async def submit(self, user_id: int, answers: StudentQuestionsAnswers, *, overwrite: bool = False) -> None:
        questions = validate_text_answer(answers.questions) if answers.had_questions else None
        found_answers = answers.found_answers if answers.had_questions else None
        if answers.had_questions and not isinstance(found_answers, bool):
            raise ValueError("Missing survey answer about finding answers")
        sources = validate_text_answer(answers.answer_sources) if found_answers else None
        response = StudentQuestionsResponse(
            user_id=user_id,
            course=StudentCourse(answers.course).value,
            had_questions=answers.had_questions,
            questions=questions,
            found_answers=found_answers,
            answer_sources=sources,
            wants_beta=answers.wants_beta,
            submitted_at=datetime.now(UTC),
        )
        if not await self._repository.save(response, overwrite=overwrite):
            raise AlreadySubmittedError
