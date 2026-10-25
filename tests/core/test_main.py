import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram import Bot

from manashelper import main as app


@pytest.mark.parametrize(
    "failure", [None, "dispatcher", "commands", "polling", "scheduler_shutdown", "container_close"]
)
async def test_resources_close_on_exit_and_failures(failure: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    load_models = Mock()
    monkeypatch.setattr(app, "load_models", load_models)
    bot = Bot(token="123456:test-token")
    close_session = AsyncMock()
    monkeypatch.setattr(bot.session, "close", close_session)
    monkeypatch.setattr(app, "Bot", Mock(return_value=bot))
    monkeypatch.setattr(app, "get_settings", Mock(return_value=SimpleNamespace(telegram_bot_token=bot.token)))

    container = SimpleNamespace(close=AsyncMock())
    dispatcher = SimpleNamespace(start_polling=AsyncMock())
    scheduler = SimpleNamespace(start=Mock(), shutdown=Mock())
    create_dispatcher = Mock(return_value=dispatcher)
    setup_commands = AsyncMock()
    monkeypatch.setattr(app, "make_async_container", Mock(return_value=container))
    monkeypatch.setattr(app, "create_dispatcher", create_dispatcher)
    monkeypatch.setattr(app, "create_scheduler", Mock(return_value=scheduler))
    monkeypatch.setattr(app, "setup_commands", setup_commands)

    failures = {
        "dispatcher": create_dispatcher,
        "commands": setup_commands,
        "polling": dispatcher.start_polling,
        "scheduler_shutdown": scheduler.shutdown,
        "container_close": container.close,
    }
    if failure is not None:
        failures[failure].side_effect = RuntimeError(failure)

    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    try:
        if failure is None:
            await app.main()
        else:
            with pytest.raises(RuntimeError, match=failure):
                await app.main()
    finally:
        loop.set_exception_handler(previous_handler)

    container.close.assert_awaited_once()
    load_models.assert_called_once_with()
    assert sum(isinstance(provider, app.CoreProvider) for provider in app.make_async_container.call_args.args) == 1
    assert sum(isinstance(provider, app.ObisProvider) for provider in app.make_async_container.call_args.args) == 1
    assert (
        sum(isinstance(provider, app.TelegramPlatformProvider) for provider in app.make_async_container.call_args.args)
        == 1
    )
    close_session.assert_awaited_once()
    if failure == "dispatcher":
        scheduler.start.assert_not_called()
        scheduler.shutdown.assert_not_called()
    else:
        scheduler.shutdown.assert_called_once()

    if failure in {"dispatcher", "commands"}:
        dispatcher.start_polling.assert_not_awaited()
    else:
        dispatcher.start_polling.assert_awaited_once_with(bot, close_bot_session=False)


async def test_model_registration_failure_happens_before_resources_are_created(monkeypatch):
    load_models = Mock(side_effect=RuntimeError("model registration failed"))
    bot, container = Mock(), Mock()
    monkeypatch.setattr(app, "load_models", load_models)
    monkeypatch.setattr(app, "Bot", bot)
    monkeypatch.setattr(app, "make_async_container", container)
    with pytest.raises(RuntimeError, match="model registration failed"):
        await app.main()
    load_models.assert_called_once_with()
    bot.assert_not_called()
    container.assert_not_called()
