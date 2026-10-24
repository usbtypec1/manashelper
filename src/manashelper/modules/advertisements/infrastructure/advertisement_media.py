import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base

if TYPE_CHECKING:
    from manashelper.modules.advertisements.infrastructure.advertisement import Advertisement


class AdvertisementMedia(Base):
    __tablename__ = "advertisement_media"
    __table_args__ = (UniqueConstraint("advertisement_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    advertisement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertisements.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(10))
    position: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advertisement: Mapped["Advertisement"] = relationship(back_populates="media")
