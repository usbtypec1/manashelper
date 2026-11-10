import asyncio
import signal
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
    monkeypatch.setattr(bot, "delete_webhook", AsyncMock())
    monkeypatch.setattr(bot.session, "close", close_session)
    monkeypatch.setattr(app, "Bot", Mock(return_value=bot))
    monkeypatch.setattr(
        app, "get_settings", Mock(return_value=SimpleNamespace(telegram_bot_token=bot.token, public_url=None))
    )

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


@pytest.mark.parametrize("registration_fails", [False, True])
async def test_webhook_registers_after_binding_and_drains_before_scope_shutdown(monkeypatch, registration_fails):
    from pydantic import SecretStr

    events = []
    bot = Bot(token="123456:development-placeholder")
    monkeypatch.setattr(bot.session, "close", AsyncMock())
    registration = AsyncMock(side_effect=RuntimeError("registration failed") if registration_fails else None)
    monkeypatch.setattr(bot, "set_webhook", registration)
    monkeypatch.setattr(app, "Bot", Mock(return_value=bot))
    settings = SimpleNamespace(
        telegram_bot_token=bot.token,
        public_url="https://example.com",
        webhook_secret=SecretStr("fixture_secret_12345678901234567890"),
        http_port=8080,
    )
    monkeypatch.setattr(app, "get_settings", lambda: settings)
    monkeypatch.setattr(app, "load_models", Mock())
    container = SimpleNamespace(close=AsyncMock(side_effect=lambda: events.append("container")))
    dispatcher = SimpleNamespace(
        emit_startup=AsyncMock(),
        emit_shutdown=AsyncMock(side_effect=lambda **kwargs: events.append("dispatcher")),
        resolve_used_update_types=Mock(return_value=["message", "callback_query"]),
        start_polling=AsyncMock(),
    )
    runner = SimpleNamespace(setup=AsyncMock(), cleanup=AsyncMock(side_effect=lambda: events.append("server")))
    monkeypatch.setattr(app, "make_async_container", Mock(return_value=container))
    monkeypatch.setattr(app, "create_dispatcher", Mock(return_value=dispatcher))
    monkeypatch.setattr(app, "create_scheduler", Mock(return_value=SimpleNamespace(start=Mock(), shutdown=Mock())))
    monkeypatch.setattr(app, "setup_commands", AsyncMock())
    monkeypatch.setattr(app, "create_web_app", Mock())
    monkeypatch.setattr(app.web, "AppRunner", Mock(return_value=runner))
    site = SimpleNamespace(start=AsyncMock())
    monkeypatch.setattr(app.web, "TCPSite", Mock(return_value=site))
    monkeypatch.setattr(app.asyncio, "Event", Mock(return_value=SimpleNamespace(wait=AsyncMock(), set=Mock())))
    loop = asyncio.get_running_loop()
    # Windows event loops lack signal handlers; this test covers ordering, not OS signal delivery.
    add_signal_handler, remove_signal_handler = Mock(), Mock()
    monkeypatch.setattr(loop, "add_signal_handler", add_signal_handler)
    monkeypatch.setattr(loop, "remove_signal_handler", remove_signal_handler)
    previous_handler = loop.get_exception_handler()
    try:
        if registration_fails:
            with pytest.raises(RuntimeError, match="registration failed"):
                await app.main()
        else:
            await app.main()
    finally:
        loop.set_exception_handler(previous_handler)
    site.start.assert_awaited_once()
    registration.assert_awaited_once_with(
        url="https://example.com/telegram/webhook",
        secret_token=settings.webhook_secret.get_secret_value(),
        allowed_updates=["message", "callback_query"],
        max_connections=10,
        drop_pending_updates=False,
    )
    dispatcher.start_polling.assert_not_awaited()
    assert events == ["server", "dispatcher", "container"]
    if not registration_fails:
        signals = [signal.SIGINT, signal.SIGTERM]
        assert [call.args[0] for call in add_signal_handler.call_args_list] == signals
        assert sorted(call.args[0] for call in remove_signal_handler.call_args_list) == sorted(signals)
