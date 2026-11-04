from dataclasses import dataclass

from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class BotStatusQuery:
    """Owns a user's delivery opt-out without changing their notification preferences."""

    users: UserRepository

    async def is_stopped(self, user_id: int) -> bool:
        user = await self.users.get_by_id(user_id)
        return user is not None and user.bot_stopped is True
