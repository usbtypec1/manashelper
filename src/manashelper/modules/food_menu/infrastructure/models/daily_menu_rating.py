import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class DailyMenuRating(Base):
    __tablename__ = "daily_menu_ratings"
    __table_args__ = (UniqueConstraint("daily_menu_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    daily_menu_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("daily_menus.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    score: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
