from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import FoodMenuCleanupSettings
from manashelper.db.models.food_menu_cleanup_settings import DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES


class FoodMenuCleanupSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_chat_id(self, chat_id: int) -> FoodMenuCleanupSettings | None:
        result = await self._session.execute(
            select(FoodMenuCleanupSettings).where(FoodMenuCleanupSettings.chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, chat_id: int) -> FoodMenuCleanupSettings:
        settings = await self.get_by_chat_id(chat_id)
        if settings is None:
            settings = FoodMenuCleanupSettings(chat_id=chat_id, delay_minutes=DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES)
            self._session.add(settings)
        return settings
