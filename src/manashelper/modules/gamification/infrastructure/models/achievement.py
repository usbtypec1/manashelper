from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, false
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.core.database import Base


class GamificationProgress(Base):
    __tablename__ = "gamification_progress"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    food_views: Mapped[int] = mapped_column(default=0, server_default="0")
    last_food_view: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    night_streak: Mapped[int] = mapped_column(default=0, server_default="0")
    last_night_date: Mapped[date | None]
    academic_marker: Mapped[str | None] = mapped_column(String(64))
    academic_term: Mapped[str | None] = mapped_column(String(32))
    gpa_baseline: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    gpa_current: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    aa_count: Mapped[int] = mapped_column(default=0, server_default="0")
    attendance_marker: Mapped[str | None] = mapped_column(String(64))
    attendance_count: Mapped[int] = mapped_column(default=0, server_default="0")


class UserAchievement(Base):
    __tablename__ = "gamification_achievements"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    achievement_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    granted_by: Mapped[int | None] = mapped_column(BigInteger)
