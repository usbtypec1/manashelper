from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from aiogram.types import CallbackQuery, Message, TelegramObject

from manashelper.bot.middlewares.rate_limit import RateLimitMiddleware


async def _handler(event: TelegramObject, data: dict[str, Any]) -> str:
    return "handled"


async def test_allows_requests_within_the_bucket_capacity() -> None:
    middleware = RateLimitMiddleware(capacity=2, refill_rate=0.0)
    message = Message.model_construct()
    data = {"event_chat": SimpleNamespace(id=1)}

    assert await middleware(_handler, message, data) == "handled"
    assert await middleware(_handler, message, data) == "handled"


async def test_rejects_once_the_bucket_is_empty_and_warns_the_chat() -> None:
    middleware = RateLimitMiddleware(capacity=1, refill_rate=0.0)
    message = Message.model_construct()
    data = {"event_chat": SimpleNamespace(id=2)}

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        assert await middleware(_handler, message, data) == "handled"
        result = await middleware(_handler, message, data)

    assert result is None
    answer.assert_awaited_once()


async def test_does_not_warn_again_within_the_cooldown() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    message = Message.model_construct()
    data = {"event_chat": SimpleNamespace(id=3)}

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        await middleware(_handler, message, data)
        await middleware(_handler, message, data)

    answer.assert_awaited_once()


async def test_answers_a_rejected_callback_query_instead_of_replying() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    callback_query = CallbackQuery.model_construct()
    data = {"event_chat": SimpleNamespace(id=4)}

    with patch.object(CallbackQuery, "answer", new_callable=AsyncMock) as answer:
        result = await middleware(_handler, callback_query, data)

    assert result is None
    answer.assert_awaited_once()


async def test_different_chats_get_independent_buckets() -> None:
    middleware = RateLimitMiddleware(capacity=1, refill_rate=0.0)
    message = Message.model_construct()

    assert await middleware(_handler, message, {"event_chat": SimpleNamespace(id=5)}) == "handled"
    assert await middleware(_handler, message, {"event_chat": SimpleNamespace(id=6)}) == "handled"


async def test_calls_handler_directly_when_there_is_no_chat() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)

    assert await middleware(_handler, TelegramObject(), {}) == "handled"
