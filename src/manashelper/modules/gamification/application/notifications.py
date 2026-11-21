from datetime import datetime
from typing import Protocol


class AchievementNotificationSender(Protocol):
    async def earned(self, user_id: int, key: str, earned_at: datetime) -> None: ...

    async def cancel(self, user_id: int, key: str) -> None: ...
