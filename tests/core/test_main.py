import asyncio
import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest
import pytest_asyncio
from aiogram import Bot

from manashelper import main as app
from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.observation import ObservationCoordinator


@pytest_asyncio.fixture
async def runtime(monkeypatch, baseline_texts):
    state = SimpleNamespace(failure=None, events=[])

    def record(name, result=None):
        def action(*args, **kwargs):
            state.events.append(name)
            if state.failure == name:
                raise RuntimeError(name)
            return result

        return Mock(side_effect=action)

    def async_record(name, result=None):
        async def action(*args, **kwargs):
            state.events.append(name)
            if state.failure == name:
                raise RuntimeError(name)
            return result

        return AsyncMock(side_effect=action)

    state.load_models = record("load_models")
    monkeypatch.setattr(app, "load_models", state.load_models)
    state.bot = Bot(token="123456:test-token")
    state.close_bot = async_record("bot_close")
    monkeypatch.setattr(state.bot.session, "close", state.close_bot)
    monkeypatch.setattr(state.bot, "set_webhook", AsyncMock())
    monkeypatch.setattr(state.bot, "delete_webhook", AsyncMock())
    monkeypatch.setattr(app, "Bot", Mock(return_value=state.bot))
    state.settings = SimpleNamespace(
        telegram_bot_token=state.bot.token,
        admin_chat_id=123456,
        telegram_transport="polling",
        http_host="127.0.0.1",
        http_port=8099,
    )
    monkeypatch.setattr(app, "get_settings", Mock(return_value=state.settings))
    state.startup = SimpleNamespace(
        restart=async_record("ui_startup"),
        install_defaults=async_record("install_defaults"),
        complete_effect=async_record("complete_effect"),
    )
    state.worker = SimpleNamespace(start=record("worker_start"), aclose=async_record("worker_close"))

    async def get(dependency):
        state.events.append("container_get")
        if dependency is EffectWorker:
            return state.worker
        if dependency in (ObservationCoordinator, FlowTelegramCoordinator):
            return state.startup
        raise AssertionError(f"Unexpected APP dependency: {dependency.__name__}")

    state.container = Mock(close=async_record("container_close"), get=AsyncMock(side_effect=get))
    scope = AsyncMock()
    scope.__aenter__.return_value = SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(current=AsyncMock(return_value=baseline_texts)))
    )
    state.container.return_value = scope
    state.dispatcher = SimpleNamespace(
        start_polling=async_record("polling"),
        emit_startup=async_record("dispatcher_startup"),
        emit_shutdown=async_record("dispatcher_shutdown"),
    )
    state.scheduler = SimpleNamespace(start=record("scheduler_start"), aclose=async_record("scheduler_close"))
    state.runner = SimpleNamespace(setup=async_record("http_setup"), cleanup=async_record("runner_cleanup"))
    state.site = SimpleNamespace(start=async_record("bind"), stop=async_record("site_stop"))
    state.http = object()
    state.create_dispatcher = record("dispatcher", state.dispatcher)
    state.create_http = record("http_app", state.http)
    state.create_scheduler = Mock(return_value=state.scheduler)
    state.create_runner = Mock(return_value=state.runner)
    state.create_site = Mock(return_value=state.site)
    state.setup_commands = async_record("commands")
    state.install_webhook = record("webhook_install")
    monkeypatch.setattr(app, "make_async_container", Mock(return_value=state.container))
    monkeypatch.setattr(app, "create_dispatcher", state.create_dispatcher)
    monkeypatch.setattr(app, "create_admin_app", state.create_http)
    monkeypatch.setattr(app, "create_scheduler", state.create_scheduler)
    monkeypatch.setattr(app.web, "AppRunner", state.create_runner)
    monkeypatch.setattr(app.web, "TCPSite", state.create_site)
    monkeypatch.setattr(app, "setup_commands", state.setup_commands)
    monkeypatch.setattr(app, "install_webhook", state.install_webhook)
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    try:
        yield state
    finally:
        loop.set_exception_handler(previous_handler)


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "ui_startup",
        "dispatcher",
        "http_app",
        "http_setup",
        "bind",
        "commands",
        "polling",
        "scheduler_close",
        "runner_cleanup",
        "container_close",
        "worker_close",
    ],
)
async def test_resources_close_on_exit_and_failures(failure, runtime):
    runtime.failure = failure
    if failure is None:
        await app.main()
    else:
        with pytest.raises(RuntimeError, match=failure):
            await app.main()

    runtime.load_models.assert_called_once_with()
    runtime.container.close.assert_awaited_once()
    runtime.close_bot.assert_awaited_once()
    providers = app.make_async_container.call_args.args
    for provider in (app.CoreProvider, app.ObisProvider, app.TelegramPlatformProvider, app.AdminUiFlowsProvider):
        assert sum(isinstance(candidate, provider) for candidate in providers) == 1
    runtime.startup.restart.assert_awaited_once()
    if failure == "ui_startup":
        runtime.startup.install_defaults.assert_not_awaited()
    else:
        runtime.startup.install_defaults.assert_awaited_once_with(123456)

    before_worker = {"ui_startup", "dispatcher"}
    if failure in before_worker:
        runtime.worker.start.assert_not_called()
        runtime.worker.aclose.assert_not_awaited()
    else:
        runtime.worker.start.assert_called_once()
        runtime.worker.aclose.assert_awaited_once()
        assert runtime.events.index("dispatcher") < runtime.events.index("worker_start")
        assert runtime.events.index("worker_close") < runtime.events.index("container_close")

    before_http = {"ui_startup", "dispatcher", "http_app"}
    if failure in before_http:
        runtime.runner.setup.assert_not_awaited()
        runtime.runner.cleanup.assert_not_awaited()
    else:
        runtime.runner.setup.assert_awaited_once()
        runtime.runner.cleanup.assert_awaited_once()
        runtime.create_runner.assert_called_once_with(
            runtime.http, access_log=None, handler_cancellation=True, shutdown_timeout=30
        )
    before_scheduler = before_http | {"http_setup", "bind"}
    if failure in before_scheduler:
        runtime.scheduler.start.assert_not_called()
        runtime.scheduler.aclose.assert_not_awaited()
        runtime.site.stop.assert_not_awaited()
    else:
        runtime.scheduler.start.assert_called_once()
        runtime.scheduler.aclose.assert_awaited_once()
        runtime.site.stop.assert_awaited_once()
        events = runtime.events
        assert events.index("site_stop") < events.index("scheduler_close") < events.index("runner_cleanup")
    if failure in before_scheduler | {"commands"}:
        runtime.dispatcher.start_polling.assert_not_awaited()
    else:
        runtime.dispatcher.start_polling.assert_awaited_once_with(runtime.bot, close_bot_session=False)
    assert runtime.events.index("container_close") < runtime.events.index("bot_close")
    runtime.install_webhook.assert_not_called()
    runtime.dispatcher.emit_startup.assert_not_awaited()
    runtime.dispatcher.emit_shutdown.assert_not_awaited()
    runtime.bot.set_webhook.assert_not_awaited()
    runtime.bot.delete_webhook.assert_not_awaited()


async def test_webhook_serves_until_signal_then_closes_without_polling_or_registration(runtime, monkeypatch):
    runtime.settings.telegram_transport = "webhook"
    loop = asyncio.get_running_loop()

    def add_signal(sig, callback):
        if sig == signal.SIGTERM:
            loop.call_soon(callback)

    add_handler = Mock(side_effect=add_signal)
    remove_handler = Mock()
    monkeypatch.setattr(loop, "add_signal_handler", add_handler)
    monkeypatch.setattr(loop, "remove_signal_handler", remove_handler)
    await asyncio.wait_for(app.main(), timeout=1)
    assert [args.args[0] for args in add_handler.call_args_list] == [signal.SIGINT, signal.SIGTERM]
    assert remove_handler.call_args_list == [call(signal.SIGTERM), call(signal.SIGINT)]
    runtime.install_webhook.assert_called_once_with(runtime.http, runtime.bot, runtime.dispatcher, runtime.settings)
    runtime.dispatcher.emit_startup.assert_awaited_once_with(bot=runtime.bot)
    runtime.dispatcher.emit_shutdown.assert_awaited_once_with(bot=runtime.bot)
    runtime.dispatcher.start_polling.assert_not_awaited()
    runtime.scheduler.start.assert_called_once()
    runtime.scheduler.aclose.assert_awaited_once()
    runtime.runner.cleanup.assert_awaited_once()
    runtime.site.stop.assert_awaited_once()
    runtime.container.close.assert_awaited_once()
    runtime.close_bot.assert_awaited_once()
    events = runtime.events
    assert events.index("dispatcher_startup") < events.index("http_setup") < events.index("commands")
    assert events.index("site_stop") < events.index("scheduler_close") < events.index("runner_cleanup")
    assert events.index("runner_cleanup") < events.index("dispatcher_shutdown") < events.index("container_close")
    runtime.worker.start.assert_called_once()
    runtime.worker.aclose.assert_awaited_once()
    assert events.index("dispatcher") < events.index("worker_start") < events.index("http_app")
    assert events.index("dispatcher_shutdown") < events.index("worker_close") < events.index("container_close")
    runtime.bot.set_webhook.assert_not_awaited()
    runtime.bot.delete_webhook.assert_not_awaited()


@pytest.mark.parametrize("failure", ["webhook_install", "dispatcher_startup", "http_setup", "bind"])
async def test_webhook_partial_startup_closes_resources_without_starting_jobs(failure, runtime):
    runtime.settings.telegram_transport = "webhook"
    runtime.failure = failure
    with pytest.raises(RuntimeError, match=failure):
        await app.main()
    runtime.container.close.assert_awaited_once()
    runtime.close_bot.assert_awaited_once()
    runtime.worker.start.assert_called_once()
    runtime.worker.aclose.assert_awaited_once()
    assert runtime.events.index("worker_close") < runtime.events.index("container_close")
    runtime.scheduler.start.assert_not_called()
    runtime.scheduler.aclose.assert_not_awaited()
    runtime.dispatcher.start_polling.assert_not_awaited()
    if failure == "webhook_install":
        runtime.dispatcher.emit_startup.assert_not_awaited()
        runtime.dispatcher.emit_shutdown.assert_not_awaited()
    else:
        runtime.dispatcher.emit_startup.assert_awaited_once_with(bot=runtime.bot)
        runtime.dispatcher.emit_shutdown.assert_awaited_once_with(bot=runtime.bot)
    if failure in {"http_setup", "bind"}:
        runtime.runner.cleanup.assert_awaited_once()
    else:
        runtime.runner.cleanup.assert_not_awaited()
    runtime.bot.set_webhook.assert_not_awaited()
    runtime.bot.delete_webhook.assert_not_awaited()


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


async def test_owned_effect_worker_finalizer_finishes_before_container_closes(runtime):
    entered, finalized = asyncio.Event(), asyncio.Event()
    worker = EffectWorker(runtime.container, Mock(), Mock())

    async def run_forever(on_result):
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            runtime.events.append("worker_finalizer")
            finalized.set()

    worker.run_forever = run_forever
    runtime.worker = worker

    async def poll(*args, **kwargs):
        await entered.wait()
        runtime.events.append("polling")

    runtime.dispatcher.start_polling.side_effect = poll
    await asyncio.wait_for(app.main(), timeout=1)
    assert finalized.is_set()
    assert runtime.events.index("worker_finalizer") < runtime.events.index("container_close")
    runtime.container.close.assert_awaited_once()
    runtime.close_bot.assert_awaited_once()


async def test_effect_worker_callback_uses_the_owned_coordinator_and_bot(runtime):
    from uuid import uuid4

    await app.main()
    operation_id = uuid4()
    callback = runtime.worker.start.call_args.args[0]
    await callback(operation_id)
    runtime.startup.complete_effect.assert_awaited_once_with(runtime.bot, operation_id)
