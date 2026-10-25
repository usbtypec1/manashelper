import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.core.database import Base

if TYPE_CHECKING:
    from manashelper.modules.schedule.infrastructure.models.course import Course
    from manashelper.modules.schedule.infrastructure.models.faculty import Faculty


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faculties.id"))

    faculty: Mapped["Faculty"] = relationship(back_populates="departments")
    courses: Mapped[list["Course"]] = relationship(back_populates="department")
