from manashelper.modules.users.infrastructure.user_repository import UserRepository


class BotStatusService:
    """Owns a user's delivery opt-out without changing their notification preferences."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def is_stopped(self, user_id: int) -> bool:
        user = await self._users.get_by_id(user_id)
        return user is not None and user.bot_stopped is True

    async def stop(self, user_id: int) -> None:
        await self._users.set_bot_stopped(user_id, True)
