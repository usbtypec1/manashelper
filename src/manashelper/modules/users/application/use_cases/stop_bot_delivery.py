from dataclasses import dataclass

from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class StopBotDeliveryUseCase:
    users: UserRepository

    async def execute(self, user_id: int) -> None:
        await self.users.set_bot_stopped(user_id, True)
