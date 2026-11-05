from datetime import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.core.database import Base


class ProcessedTelegramUpdate(Base):
    __tablename__ = "telegram_processed_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
