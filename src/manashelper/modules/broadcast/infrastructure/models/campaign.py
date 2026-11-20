from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.core.database import Base


class BroadcastCampaign(Base):
    __tablename__ = "broadcast_campaigns"
    __table_args__ = (Index("ix_broadcast_campaigns_created_at_id", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    audience: Mapped[str] = mapped_column(String(16))
    user_ids: Mapped[list[int]] = mapped_column(JSONB)
    variants: Mapped[list[dict[str, str | None]]] = mapped_column(JSONB)
