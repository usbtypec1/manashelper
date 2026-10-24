from manashelper.repositories.user_repository import UserRepository


class UsersQuery:
    """Public read operations returning identifiers and counts without ORM objects."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def count(self) -> int:
        return await self._users.count()

    async def get_all_ids(self) -> list[int]:
        return await self._users.get_all_ids()
