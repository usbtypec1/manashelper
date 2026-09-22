import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class ActionLog(Base):
    """One row per message/callback_query update, written by `ActionLogMiddleware` before the
    update reaches its handler — see `bot/middlewares/action_log.py`."""

    __tablename__ = "action_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    callback_query_data: Mapped[str | None] = mapped_column(Text)
    message_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
