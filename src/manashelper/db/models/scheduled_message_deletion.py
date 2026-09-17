import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class ScheduledMessageDeletion(Base):
    """An outbox row: "delete this message at this time". Cleaned up by `cleanup_scheduled_message_deletions_job`
    regardless of whether the Telegram delete call actually succeeds — see scheduler_jobs.py."""

    __tablename__ = "scheduled_message_deletions"
    __table_args__ = (Index("ix_scheduled_message_deletions_delete_at", "delete_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    delete_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
