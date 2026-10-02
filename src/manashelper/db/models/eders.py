from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.db.base import Base


class EdersState(Base):
    __tablename__ = "eders_states"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    credential_marker: Mapped[str | None] = mapped_column(String(64))
    snapshot: Mapped[str | None] = mapped_column(Text)
    day_before: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    two_hours_before: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    openings: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    deadline_changes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    hide_archived: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    new_materials: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    grade_changes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class EdersNotification(Base):
    __tablename__ = "eders_notifications"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    activity_key: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[str] = mapped_column(Text)
    previous_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
