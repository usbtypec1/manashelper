from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base
from manashelper.db.models.associations import user_courses

if TYPE_CHECKING:
    from manashelper.db.models.course import Course


class UserRole(StrEnum):
    USER = "user"
    MARKETPLACE_ADMIN = "marketplace_admin"
    SUPERADMIN = "superadmin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(128))
    student_number: Mapped[str | None] = mapped_column(String(32))
    encrypted_password: Mapped[str | None] = mapped_column(String(255))
    # Stores a Locale.value (e.g. "ru"). NULL means the locale couldn't be auto-detected from
    # the Telegram client yet and the user hasn't picked one either — see
    # bot/middlewares/i18n.py.
    locale: Mapped[str | None] = mapped_column(String(2))
    # Stores a UserRole.value. Assigned by hand directly in Postgres by an operator — there is no
    # in-bot role management UI (see the advertising platform's moderation flow, the only feature
    # that reads this today).
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value, server_default=UserRole.USER.value)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    tracked_courses: Mapped[list["Course"]] = relationship(secondary=user_courses, back_populates="users")
