from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    sent: int
    total: int


class BroadcastSender(Protocol):
    async def send(self, user_id: int, body: str) -> bool: ...
