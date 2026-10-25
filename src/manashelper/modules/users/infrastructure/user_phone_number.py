import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class UserPhoneNumber(Base):
    __tablename__ = "user_phone_numbers"
    __table_args__ = (UniqueConstraint("user_id", "phone_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    phone_number: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
