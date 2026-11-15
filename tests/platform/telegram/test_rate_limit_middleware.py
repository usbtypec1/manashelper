from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.enums import ChatType, ParseMode
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject, User

from manashelper.platform.telegram.middlewares.rate_limit import RateLimitMiddleware


async def _handler(event: TelegramObject, data: dict[str, Any]) -> str:
    return "handled"


async def test_allows_requests_within_the_bucket_capacity() -> None:
    middleware = RateLimitMiddleware(capacity=2, refill_rate=0.0)
    message = Message.model_construct(chat=Chat(id=1, type=ChatType.PRIVATE))
    data = {"event_chat": SimpleNamespace(id=1)}

    assert await middleware(_handler, message, data) == "handled"
    assert await middleware(_handler, message, data) == "handled"


async def test_rejects_once_the_bucket_is_empty_and_warns_the_chat() -> None:
    middleware = RateLimitMiddleware(capacity=1, refill_rate=0.0)
    message = Message.model_construct(
        chat=Chat(id=2, type=ChatType.PRIVATE),
        from_user=User(id=2, is_bot=False, first_name="Student", username="student"),
    )
    data = {"event_chat": SimpleNamespace(id=2)}

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        assert await middleware(_handler, message, data) == "handled"
        result = await middleware(_handler, message, data)

    assert result is None
    answer.assert_awaited_once_with("⏳ Слишком много запросов подряд. Подождите немного.")


async def test_does_not_warn_again_within_the_cooldown() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    message = Message.model_construct(chat=Chat(id=3, type=ChatType.PRIVATE))
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
    answer.assert_awaited_once_with("⏳ Слишком много запросов подряд. Подождите немного.", show_alert=False)


async def test_different_chats_get_independent_buckets() -> None:
    middleware = RateLimitMiddleware(capacity=1, refill_rate=0.0)
    message = Message.model_construct(chat=Chat(id=5, type=ChatType.PRIVATE))

    assert await middleware(_handler, message, {"event_chat": SimpleNamespace(id=5)}) == "handled"
    assert await middleware(_handler, message, {"event_chat": SimpleNamespace(id=6)}) == "handled"


async def test_calls_handler_directly_when_there_is_no_chat() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)

    assert await middleware(_handler, TelegramObject(), {}) == "handled"


@pytest.mark.parametrize("chat_type", [ChatType.GROUP, ChatType.SUPERGROUP])
@pytest.mark.parametrize(
    ("username", "expected_sender"),
    [("student", "@student"), (None, "&lt;Student&gt; &amp; Family")],
)
async def test_group_warning_identifies_the_sender(
    chat_type: ChatType, username: str | None, expected_sender: str
) -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    chat = Chat(id=-100123, type=chat_type)
    user = User(id=123456789, is_bot=False, first_name="<Student>", last_name="& Family", username=username)
    message = Message.model_construct(chat=chat, from_user=user)

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        assert await middleware(_handler, message, {"event_chat": chat}) is None

    answer.assert_awaited_once_with(
        f"{expected_sender} (ID: <code>123456789</code>)\n⏳ Слишком много запросов подряд. Подождите немного.",
        parse_mode=ParseMode.HTML,
    )


async def test_group_warning_identifies_sender_chat_instead_of_anonymous_bot() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    chat = Chat(id=-100123, type=ChatType.SUPERGROUP, title="<Study> & Group")
    anonymous_bot = User(id=1087968824, is_bot=True, first_name="Group", username="GroupAnonymousBot")
    message = Message.model_construct(chat=chat, from_user=anonymous_bot, sender_chat=chat)

    with patch.object(Message, "answer", new_callable=AsyncMock) as answer:
        await middleware(_handler, message, {"event_chat": chat})

    answer.assert_awaited_once_with(
        "&lt;Study&gt; &amp; Group (ID: <code>-100123</code>)\n⏳ Слишком много запросов подряд. Подождите немного.",
        parse_mode=ParseMode.HTML,
    )


async def test_group_warning_cooldown_is_shared_between_senders_and_expires() -> None:
    middleware = RateLimitMiddleware(capacity=0, refill_rate=0.0)
    chat = Chat(id=-100123, type=ChatType.SUPERGROUP)
    first = Message.model_construct(chat=chat, from_user=User(id=1, is_bot=False, first_name="First"))
    second = Message.model_construct(chat=chat, from_user=User(id=2, is_bot=False, first_name="Second"))

    with (
        patch("manashelper.platform.telegram.middlewares.rate_limit.time.monotonic", return_value=100.0) as monotonic,
        patch.object(Message, "answer", new_callable=AsyncMock) as answer,
    ):
        await middleware(_handler, first, {"event_chat": chat})
        monotonic.return_value = 101.0
        await middleware(_handler, second, {"event_chat": chat})
        assert answer.await_count == 1

        monotonic.return_value = 103.0
        await middleware(_handler, second, {"event_chat": chat})
        assert answer.await_count == 2

    assert answer.await_args is not None
    assert answer.await_args.args[0].startswith("Second (ID: <code>2</code>)")
