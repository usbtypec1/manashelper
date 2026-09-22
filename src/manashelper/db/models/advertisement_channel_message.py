import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base

if TYPE_CHECKING:
    from manashelper.db.models.advertisement import Advertisement


class AdvertisementChannelMessage(Base):
    __tablename__ = "advertisement_channel_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    advertisement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertisements.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advertisement: Mapped["Advertisement"] = relationship(back_populates="channel_messages")
