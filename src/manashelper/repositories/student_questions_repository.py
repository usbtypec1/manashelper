from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import StudentQuestionsResponse


class StudentQuestionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_response(self, user_id: int) -> bool:
        result = await self._session.scalar(
            select(StudentQuestionsResponse.user_id).where(StudentQuestionsResponse.user_id == user_id)
        )
        return result is not None

    async def save(self, response: StudentQuestionsResponse, *, overwrite: bool) -> bool:
        values = {
            "user_id": response.user_id,
            "course": response.course,
            "had_questions": response.had_questions,
            "questions": response.questions,
            "found_answers": response.found_answers,
            "answer_sources": response.answer_sources,
            "wants_beta": response.wants_beta,
            "submitted_at": response.submitted_at,
        }
        statement = insert(StudentQuestionsResponse).values(**values)
        if overwrite:
            statement = statement.on_conflict_do_update(
                index_elements=[StudentQuestionsResponse.user_id],
                set_={key: value for key, value in values.items() if key != "user_id"},
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=[StudentQuestionsResponse.user_id])
        result = await self._session.scalar(statement.returning(StudentQuestionsResponse.user_id))
        return result is not None
