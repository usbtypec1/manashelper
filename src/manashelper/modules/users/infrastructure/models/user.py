from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.core.database import Base
from manashelper.modules.schedule.infrastructure.models.associations import user_courses

if TYPE_CHECKING:
    from manashelper.modules.schedule.infrastructure.models.course import Course


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    student_number: Mapped[str | None] = mapped_column(String(32))
    encrypted_password: Mapped[str | None] = mapped_column(String(255))
    # Stores a Locale.value (e.g. "ru"). NULL means the locale couldn't be auto-detected from
    # the Telegram client yet and the user hasn't picked one either — see
    # bot/middlewares/i18n.py; locale selection lives in Users presentation.
    locale: Mapped[str | None] = mapped_column(String(2))
    theme: Mapped[str] = mapped_column(String(16), default="basic", server_default="basic")
    bot_stopped: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tracked_courses: Mapped[list["Course"]] = relationship(secondary=user_courses, back_populates="users")
