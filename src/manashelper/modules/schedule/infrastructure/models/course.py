import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.core.database import Base
from manashelper.modules.schedule.infrastructure.models.associations import user_courses

if TYPE_CHECKING:
    from manashelper.modules.schedule.infrastructure.models.department import Department
    from manashelper.modules.users.infrastructure.user import User


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    number: Mapped[int]
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id"))

    department: Mapped["Department"] = relationship(back_populates="courses")
    users: Mapped[list["User"]] = relationship(secondary=user_courses, back_populates="tracked_courses")
