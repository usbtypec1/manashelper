from dataclasses import dataclass

from manashelper.modules.users.infrastructure.repositories.user import UserRepository


@dataclass(frozen=True, slots=True)
class SetUserBlockedUseCase:
    users: UserRepository

    async def execute(self, user_id: int, *, blocked: bool) -> bool:
        return await self.users.set_blocked(user_id, blocked)
