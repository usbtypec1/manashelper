from manashelper.modules.users.infrastructure.repositories.user import UserRepository


class UsersQuery:
    """Public read operations returning identifiers and counts without ORM objects."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def count(self) -> int:
        return await self._users.count()

    async def get_all_ids(self) -> list[int]:
        return await self._users.get_all_ids()

    async def get_active_ids(self) -> list[int]:
        return await self._users.get_active_ids()

    async def exists(self, user_id: int) -> bool:
        return await self._users.get_by_id(user_id) is not None

    async def get_username(self, user_id: int) -> str | None:
        user = await self._users.get_by_id(user_id)
        return user.username if user is not None else None
