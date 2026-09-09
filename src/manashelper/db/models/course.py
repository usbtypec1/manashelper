import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.db.base import Base
from manashelper.db.models.associations import user_courses

if TYPE_CHECKING:
    from manashelper.db.models.department import Department
    from manashelper.db.models.user import User


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    number: Mapped[int]
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"))

    department: Mapped["Department"] = relationship(back_populates="courses")
    users: Mapped[list["User"]] = relationship(secondary=user_courses, back_populates="tracked_courses")
