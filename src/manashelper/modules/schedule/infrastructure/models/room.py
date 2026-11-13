from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.core.database import Base


class Room(Base):
    """Room catalog from the timetable site; lessons reference rooms only by printed name."""

    __tablename__ = "timetable_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(128))
    capacity: Mapped[int]
    room_key: Mapped[str] = mapped_column(String(128), index=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
