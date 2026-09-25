from manashelper.repositories.user_repository import UserRepository


class BroadcastService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def get_recipient_ids(self) -> list[int]:
        return await self._user_repository.get_all_ids()
