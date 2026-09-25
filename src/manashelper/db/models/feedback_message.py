import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class FeedbackMessage(Base):
    __tablename__ = "feedback_messages"
    __table_args__ = (Index("ix_feedback_messages_admin_chat_message_id", "admin_chat_message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(String(2000))
    # The id of the message this feedback was forwarded as in `Settings.admin_chat_id` - an admin's
    # native Telegram "reply" to that message is how their answer gets matched back to this row (and
    # thus to `user_id`), rather than any in-bot reply UI. NULL only for the brief window between
    # inserting the row and the forward actually landing.
    admin_chat_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
