from dataclasses import dataclass

from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class UsersQuery:
    """Public read operations returning identifiers and counts without ORM objects."""

    users: UserRepository

    async def count(self) -> int:
        return await self.users.count()

    async def get_all_ids(self) -> list[int]:
        return await self.users.get_all_ids()

    async def get_active_ids(self) -> list[int]:
        return await self.users.get_active_ids()

    async def exists(self, user_id: int) -> bool:
        return await self.users.get_by_id(user_id) is not None

    async def get_username(self, user_id: int) -> str | None:
        user = await self.users.get_by_id(user_id)
        return user.username if user is not None else None
