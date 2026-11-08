import uuid
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.core.database import Base


class Dish(Base):
    __tablename__ = "food_dishes"
    # Preserve the existing index name when renaming the Turkish name column.
    __table_args__ = (Index("ix_dishes_name", "name_tr", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name_tr: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    name_ky: Mapped[str | None] = mapped_column(String(255))
    name_zh: Mapped[str | None] = mapped_column(String(255))
    photo_url: Mapped[str] = mapped_column(String(255))
    upscaled_photo_url: Mapped[str | None] = mapped_column(String(2048))
    calories: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
