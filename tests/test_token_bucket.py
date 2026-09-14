import pytest

from manashelper.bot.middlewares import token_bucket as token_bucket_module
from manashelper.bot.middlewares.token_bucket import TokenBucket


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    state = {"now": 0.0}
    monkeypatch.setattr(token_bucket_module.time, "monotonic", lambda: state["now"])
    return state


def test_allows_burst_up_to_capacity(clock: dict[str, float]) -> None:
    bucket = TokenBucket(capacity=3, refill_rate=1.0)

    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False


def test_refills_over_time_at_the_configured_rate(clock: dict[str, float]) -> None:
    bucket = TokenBucket(capacity=1, refill_rate=1.0)
    assert bucket.try_consume() is True
    assert bucket.try_consume() is False

    clock["now"] += 0.5
    assert bucket.try_consume() is False

    clock["now"] += 0.5
    assert bucket.try_consume() is True


def test_refill_never_exceeds_capacity(clock: dict[str, float]) -> None:
    bucket = TokenBucket(capacity=2, refill_rate=5.0)

    clock["now"] += 100.0
    assert bucket.try_consume(tokens=2) is True
    assert bucket.try_consume() is False


def test_can_consume_more_than_one_token_at_once(clock: dict[str, float]) -> None:
    bucket = TokenBucket(capacity=5, refill_rate=1.0)

    assert bucket.try_consume(tokens=5) is True
    assert bucket.try_consume(tokens=1) is False
