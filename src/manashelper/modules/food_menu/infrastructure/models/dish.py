import uuid
from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.core.database import Base


class Dish(Base):
    __tablename__ = "food_dishes"
    # Keep the existing index name: the migration renames tables only.
    __table_args__ = (Index("ix_dishes_name", "name", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    photo_url: Mapped[str] = mapped_column(String(255))
    calories: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
