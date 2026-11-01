from ui_flows.ports.repositories import LocationStore


class LocationService:
    def __init__(self, repository: LocationStore) -> None:
        self._repository = repository

    async def observe(self, user_id: int, chat_id: int, update_id: int, handler: str, state: str | None) -> None:
        if user_id <= 0 or chat_id != user_id:
            return
        await self._repository.observe(user_id, chat_id, update_id, handler[:200], state[:200] if state else None)

    async def forget_legacy(self) -> None:
        await self._repository.forget_legacy()
