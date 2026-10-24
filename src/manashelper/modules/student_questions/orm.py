from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class StudentQuestionsResponse(Base):
    __tablename__ = "student_questions_responses"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True, autoincrement=False)
    course: Mapped[str] = mapped_column(String(16))
    had_questions: Mapped[bool]
    questions: Mapped[str | None] = mapped_column(Text)
    found_answers: Mapped[bool | None]
    answer_sources: Mapped[str | None] = mapped_column(Text)
    wants_beta: Mapped[bool]
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
