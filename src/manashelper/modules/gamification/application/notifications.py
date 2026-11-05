from typing import Protocol


class AchievementNotificationSender(Protocol):
    async def earned(self, user_id: int, key: str) -> None: ...
