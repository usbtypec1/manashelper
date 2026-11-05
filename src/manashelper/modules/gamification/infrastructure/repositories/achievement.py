import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.gamification.infrastructure.models.achievement import GamificationProgress, UserAchievement
from manashelper.modules.users.infrastructure.models.user import User


@dataclass(frozen=True, slots=True)
class AchievementRepository:
    session: AsyncSession

    async def is_enabled(self, user_id: int) -> bool:
        return bool(
            await self.session.scalar(
                select(GamificationProgress.enabled).where(GamificationProgress.user_id == user_id)
            )
        )

    async def lock_progress(self, user_id: int, *, require_enabled: bool = True) -> GamificationProgress | None:
        # Lock our own row; never take the user lock held across an OBIS HTTP fetch.
        exists = await self.session.scalar(select(User.id).where(User.id == user_id))
        if exists is None:
            return None
        if not require_enabled:
            await self.session.execute(insert(GamificationProgress).values(user_id=user_id).on_conflict_do_nothing())
        result = await self.session.execute(
            select(GamificationProgress).where(GamificationProgress.user_id == user_id).with_for_update()
        )
        progress = result.scalar_one_or_none()
        return progress if progress is not None and (progress.enabled or not require_enabled) else None

    async def set_enabled(self, user_id: int, enabled: bool) -> None:
        progress = await self.lock_progress(user_id, require_enabled=False)
        if progress is None:
            raise LookupError("User is not registered")
        progress.enabled = enabled
        await self.session.flush()

    async def award(self, user_id: int, key: str, now: datetime, granted_by: int | None = None) -> bool:
        if await self.lock_progress(user_id) is None:
            return False
        result = await self.session.scalar(
            insert(UserAchievement)
            .values(user_id=user_id, achievement_key=key, earned_at=now, granted_by=granted_by)
            .on_conflict_do_nothing()
            .returning(UserAchievement.achievement_key)
        )
        return result is not None

    async def get_progress(self, user_id: int) -> tuple[int, int, date | None]:
        row = await self.session.get(GamificationProgress, user_id)
        return (row.food_views, row.night_streak, row.last_night_date) if row else (0, 0, None)

    async def get_awards(self, user_id: int) -> dict[str, datetime]:
        rows = await self.session.execute(
            select(UserAchievement.achievement_key, UserAchievement.earned_at).where(UserAchievement.user_id == user_id)
        )
        return {key: earned_at for key, earned_at in rows}

    async def academic_progress(self, user_id: int) -> tuple[bool, Decimal | None, Decimal | None, int]:
        row = await self.session.get(GamificationProgress, user_id)
        student_number = await self.session.scalar(select(User.student_number).where(User.id == user_id))
        if (
            row is None
            or not student_number
            or row.academic_marker != hashlib.sha256(student_number.encode()).hexdigest()
        ):
            return False, None, None, 0
        return True, row.gpa_baseline, row.gpa_current, row.aa_count

    async def attendance_progress(self, user_id: int) -> tuple[bool, int]:
        row = await self.session.get(GamificationProgress, user_id)
        student_number = await self.session.scalar(select(User.student_number).where(User.id == user_id))
        if (
            row is None
            or not student_number
            or row.attendance_marker != hashlib.sha256(student_number.encode()).hexdigest()
        ):
            return False, 0
        return True, row.attendance_count

    async def ranking(self, user_id: int | None = None) -> list[tuple[int, str, int, int]]:
        # Ties share a place; SQL limits the result rather than loading every user.
        totals = (
            select(
                UserAchievement.user_id,
                func.count().label("score"),
                func.max(UserAchievement.earned_at).label("reached_at"),
            )
            .group_by(UserAchievement.user_id)
            .subquery()
        )
        ranked = (
            select(
                User.id,
                User.full_name,
                totals.c.score,
                func.rank().over(order_by=totals.c.score.desc()).label("place"),
                totals.c.reached_at,
            )
            .join(totals, totals.c.user_id == User.id)
            .join(GamificationProgress, GamificationProgress.user_id == User.id)
            .where(GamificationProgress.enabled.is_(True))
            .subquery()
        )
        statement = select(ranked.c.id, ranked.c.full_name, ranked.c.score, ranked.c.place)
        if user_id is None:
            statement = statement.order_by(ranked.c.score.desc(), ranked.c.reached_at, ranked.c.id).limit(10)
        else:
            statement = statement.where(ranked.c.id == user_id)
        rows = await self.session.execute(statement)
        return [(user_id, name, int(score), int(rank)) for user_id, name, score, rank in rows]
