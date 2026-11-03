import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.core.database import Base
from manashelper.modules.advertisements.domain.enums import AdvertisementStatus

if TYPE_CHECKING:
    from manashelper.modules.advertisements.infrastructure.models.advertisement_channel_message import (
        AdvertisementChannelMessage,
    )
    from manashelper.modules.advertisements.infrastructure.models.advertisement_media import AdvertisementMedia


class Advertisement(Base):
    __tablename__ = "advertisement_ads"
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
    # New ads contain one entered number; historical ads retain all saved contacts.
    phone_numbers: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
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
