import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class UserLessonAttendance(Base):
    __tablename__ = "user_lesson_attendance"
    __table_args__ = (UniqueConstraint("user_id", "lesson_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    lesson_code: Mapped[str] = mapped_column(String(32))
    theory_skips_percentage: Mapped[float | None] = mapped_column(Float)
    practice_skips_percentage: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
