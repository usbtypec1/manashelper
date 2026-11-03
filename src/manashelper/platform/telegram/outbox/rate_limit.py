from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TokenBucket:
    rate: float
    capacity: float

    def refill(self, tokens: float, updated_at: datetime, now: datetime) -> float:
        return min(self.capacity, tokens + max(0.0, (now - updated_at).total_seconds()) * self.rate)

    def delay(self, tokens: float) -> float:
        return max(0.0, (1.0 - tokens) / self.rate)


# Leave room for interactive replies within Telegram's free broadcast allowance.
GLOBAL_BUCKET = TokenBucket(rate=20.0, capacity=5.0)
CHAT_BUCKET = TokenBucket(rate=1.0, capacity=1.0)
GROUP_BUCKET = TokenBucket(rate=1.0 / 3.0, capacity=1.0)
