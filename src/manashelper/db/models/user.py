from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base
from manashelper.db.models.associations import user_courses

if TYPE_CHECKING:
    from manashelper.db.models.course import Course


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    student_number: Mapped[str | None] = mapped_column(String(32))
    encrypted_password: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tracked_courses: Mapped[list["Course"]] = relationship(secondary=user_courses, back_populates="users")
