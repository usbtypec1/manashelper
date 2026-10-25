import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import FoodMenuNotificationSettings, User

WEEKDAYS = range(7)


class FoodMenuNotificationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user_id(self, user_id: int) -> list[FoodMenuNotificationSettings]:
        result = await self._session.execute(
            select(FoodMenuNotificationSettings).where(FoodMenuNotificationSettings.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_or_create(self, user_id: int, weekday: int) -> FoodMenuNotificationSettings:
        result = await self._session.execute(
            select(FoodMenuNotificationSettings).where(
                FoodMenuNotificationSettings.user_id == user_id,
                FoodMenuNotificationSettings.weekday == weekday,
            )
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = FoodMenuNotificationSettings(id=uuid.uuid4(), user_id=user_id, weekday=weekday)
            self._session.add(settings)
        return settings

    async def reset_to_default(self, user_id: int) -> None:
        await self._session.execute(
            delete(FoodMenuNotificationSettings).where(FoodMenuNotificationSettings.user_id == user_id)
        )

    async def disable_all(self, user_id: int) -> None:
        for weekday in WEEKDAYS:
            settings = await self.get_or_create(user_id, weekday)
            settings.lunch_enabled = False
            settings.dinner_enabled = False

    async def get_user_ids_with_lunch_enabled_for_weekday(self, weekday: int) -> list[int]:
        return await self._get_user_ids_with_enabled_for_weekday(weekday, lunch=True)

    async def get_user_ids_with_dinner_enabled_for_weekday(self, weekday: int) -> list[int]:
        return await self._get_user_ids_with_enabled_for_weekday(weekday, lunch=False)

    async def _get_user_ids_with_enabled_for_weekday(self, weekday: int, *, lunch: bool) -> list[int]:
        column = FoodMenuNotificationSettings.lunch_enabled if lunch else FoodMenuNotificationSettings.dinner_enabled
        result = await self._session.execute(
            select(User.id)
            .outerjoin(
                FoodMenuNotificationSettings,
                (FoodMenuNotificationSettings.user_id == User.id) & (FoodMenuNotificationSettings.weekday == weekday),
            )
            .where(column.is_distinct_from(False))
        )
        return list(result.scalars().all())
