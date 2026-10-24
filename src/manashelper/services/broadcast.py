from manashelper.modules.users.queries import UsersQuery


class BroadcastService:
    def __init__(self, users: UsersQuery) -> None:
        self._users = users

    async def get_recipient_ids(self) -> list[int]:
        return await self._users.get_all_ids()
