import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class UserExamGrade(Base):
    __tablename__ = "user_exam_grades"
    __table_args__ = (UniqueConstraint("user_id", "lesson_code", "exam_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    lesson_code: Mapped[str | None] = mapped_column(String(32))
    exam_name: Mapped[str | None] = mapped_column(String(128))
    score: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
