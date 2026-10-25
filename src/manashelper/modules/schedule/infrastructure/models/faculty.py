import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.core.database import Base

if TYPE_CHECKING:
    from manashelper.modules.schedule.infrastructure.models.department import Department


class Faculty(Base):
    __tablename__ = "faculties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))

    departments: Mapped[list["Department"]] = relationship(back_populates="faculty")
