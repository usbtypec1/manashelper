import time


class TokenBucket:
    """Classic token-bucket rate limiter.

    Holds up to `capacity` tokens, refilled continuously at `refill_rate` tokens per second.
    This allows short bursts up to `capacity` while capping sustained throughput at
    `refill_rate` — unlike a fixed window, there's no boundary where a user could burn a full
    window's worth of requests in its last instant and another full window's worth right after.
    """

    def __init__(self, capacity: int, refill_rate: float) -> None:
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()

    def try_consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        self._tokens = min(
            float(self._capacity),
            self._tokens + (now - self._last_refill) * self._refill_rate,
        )
        self._last_refill = now

        if self._tokens < tokens:
            return False

        self._tokens -= tokens
        return True
