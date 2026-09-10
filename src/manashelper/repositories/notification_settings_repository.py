from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import NotificationSettings


class NotificationSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: int) -> NotificationSettings:
        settings = await self._session.get(NotificationSettings, user_id)
        if settings is None:
            settings = NotificationSettings(user_id=user_id)
            self._session.add(settings)
        return settings
