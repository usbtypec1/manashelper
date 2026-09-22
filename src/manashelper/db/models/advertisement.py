import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base

if TYPE_CHECKING:
    from manashelper.db.models.advertisement_channel_message import AdvertisementChannelMessage
    from manashelper.db.models.advertisement_media import AdvertisementMedia


class AdvertisementStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class Advertisement(Base):
    __tablename__ = "advertisements"
    __table_args__ = (
        Index("ix_advertisements_user_id", "user_id"),
        Index("ix_advertisements_status", "status"),
        Index("ix_advertisements_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(512))
    price: Mapped[int | None]
    status: Mapped[str] = mapped_column(
        String(20), default=AdvertisementStatus.PENDING.value, server_default=AdvertisementStatus.PENDING.value
    )
    rejection_comment: Mapped[str | None] = mapped_column(String(512))
    expires_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    media: Mapped[list["AdvertisementMedia"]] = relationship(
        back_populates="advertisement", order_by="AdvertisementMedia.position", cascade="all, delete-orphan"
    )
    channel_messages: Mapped[list["AdvertisementChannelMessage"]] = relationship(
        back_populates="advertisement", cascade="all, delete-orphan"
    )
