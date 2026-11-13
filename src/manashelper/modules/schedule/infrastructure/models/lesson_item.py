import uuid

from sqlalchemy import ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.core.database import Base


class LessonItem(Base):
    """One lesson inside a timetable slot; a slot can hold several parallel sections."""

    __tablename__ = "timetable_lesson_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("timetable_lessons.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(Text)
    teacher: Mapped[str] = mapped_column(Text)
    room: Mapped[str] = mapped_column(Text)
    teacher_key: Mapped[str] = mapped_column(Text, index=True)
    room_key: Mapped[str] = mapped_column(String(128), index=True)
    subject_key: Mapped[str | None] = mapped_column(String(64), index=True)
