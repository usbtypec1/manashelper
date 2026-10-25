from manashelper.modules.users.queries import UsersQuery


class DonationService:
    def __init__(self, users: UsersQuery) -> None:
        self._users = users

    async def other_users_count(self) -> int:
        return max(0, await self._users.count() - 1)
