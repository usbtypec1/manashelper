import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class FoodMenuNotificationSettings(Base):
    __tablename__ = "food_menu_notification_settings"
    __table_args__ = (UniqueConstraint("user_id", "weekday"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    lunch_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    dinner_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
