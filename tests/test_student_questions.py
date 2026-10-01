from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import StudentQuestionsResponse, User
from manashelper.repositories.student_questions_repository import StudentQuestionsRepository
from manashelper.services.student_questions import (
    ANSWER_MAX_LENGTH,
    AlreadySubmittedError,
    StudentCourse,
    StudentQuestionsAnswers,
    StudentQuestionsService,
    validate_text_answer,
)

USER_ID = 990_001
ANSWERS = StudentQuestionsAnswers(StudentCourse.PREPARATORY, True, " How to apply? ", True, " University site ", True)


async def _service(session: AsyncSession) -> StudentQuestionsService:
    session.add(User(id=USER_ID, full_name="Survey tester"))
    await session.flush()
    return StudentQuestionsService(StudentQuestionsRepository(session))


async def _response(session: AsyncSession) -> StudentQuestionsResponse:
    result = await session.scalar(select(StudentQuestionsResponse).execution_options(populate_existing=True))
    assert result is not None
    return result


async def test_completed_response_is_saved_and_duplicate_does_not_overwrite(session: AsyncSession) -> None:
    service = await _service(session)
    assert not await service.has_submitted(USER_ID)
    await service.submit(USER_ID, ANSWERS)
    assert await service.has_submitted(USER_ID)
    with pytest.raises(AlreadySubmittedError):
        await service.submit(USER_ID, replace(ANSWERS, course=StudentCourse.YEAR_5, wants_beta=False))
    saved = await _response(session)
    assert saved.user_id == USER_ID and saved.course == "preparatory"
    assert saved.had_questions and saved.questions == "How to apply?"
    assert saved.found_answers and saved.answer_sources == "University site"
    assert saved.wants_beta and saved.submitted_at.tzinfo is not None
    assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1


async def test_explicit_overwrite_replaces_all_fields_and_clears_skipped_answers(session: AsyncSession) -> None:
    service = await _service(session)
    await service.submit(USER_ID, ANSWERS)
    timestamp = (await _response(session)).submitted_at
    await service.submit(
        USER_ID,
        replace(ANSWERS, course=StudentCourse.NOT_STUDENT, had_questions=False, wants_beta=False),
        overwrite=True,
    )
    saved = await _response(session)
    assert saved.course == "not_student" and not saved.had_questions and not saved.wants_beta
    assert saved.questions is None and saved.found_answers is None and saved.answer_sources is None
    assert saved.submitted_at >= timestamp
    assert await session.scalar(select(func.count()).select_from(StudentQuestionsResponse)) == 1


async def test_unanswered_questions_skip_answer_sources(session: AsyncSession) -> None:
    service = await _service(session)
    await service.submit(USER_ID, replace(ANSWERS, found_answers=False))
    saved = await _response(session)
    assert saved.questions == "How to apply?" and saved.found_answers is False
    assert saved.answer_sources is None


@pytest.mark.parametrize("changes", [{"questions": ""}, {"found_answers": None}, {"answer_sources": " "}])
async def test_invalid_required_answers_are_not_saved(changes) -> None:
    repository = AsyncMock()
    with pytest.raises(ValueError):
        await StudentQuestionsService(repository).submit(USER_ID, replace(ANSWERS, **changes))
    repository.save.assert_not_awaited()


@pytest.mark.parametrize("text", [None, "", " \n ", "x" * (ANSWER_MAX_LENGTH + 1)])
def test_text_validation_rejects_missing_or_excessive_input(text) -> None:
    with pytest.raises(ValueError):
        validate_text_answer(text)


def test_text_validation_preserves_content_and_accepts_limit() -> None:
    assert validate_text_answer("  <b>Question?</b>\nSecond question  ") == "<b>Question?</b>\nSecond question"
    assert validate_text_answer("x" * ANSWER_MAX_LENGTH) == "x" * ANSWER_MAX_LENGTH
