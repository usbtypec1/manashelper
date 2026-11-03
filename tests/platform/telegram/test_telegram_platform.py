import asyncio
import importlib.util
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, User
from dishka import make_async_container
from dishka.integrations.aiogram import CONTAINER_NAME
from sqlalchemy.ext.asyncio import AsyncSession

import manashelper
from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.jobs.scheduler import create_scheduler
from manashelper.platform.i18n import catalog as catalog
from manashelper.platform.telegram import command_catalog
from manashelper.platform.telegram.audit.orm import ActionLog
from manashelper.platform.telegram.audit.repository import ActionLogRepository
from manashelper.platform.telegram.audit.service import ActionLogService
from manashelper.platform.telegram.middlewares.action_log import ActionLogMiddleware
from manashelper.platform.telegram.middlewares.per_chat_ordering import PerChatOrderingMiddleware
from manashelper.platform.telegram.middlewares.private_chat_only import PrivateChatOnlyMiddleware
from manashelper.platform.telegram.provider import TelegramPlatformProvider


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=974001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="platform", from_user=user, message=message, chat_instance="chat").as_(bot)
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    with catalog.i18n.context(), catalog.i18n.use_locale("ru"):
        yield SimpleNamespace(message=message, callback=callback, request=request)


@pytest.mark.parametrize("kind", ["text", "caption", "masked", "callback", "empty", "no_chat", "no_user"])
async def test_audit_persists_exact_update_data_before_handler(session, context, kind):
    service = ActionLogService(ActionLogRepository(session))
    request = SimpleNamespace(get=AsyncMock(return_value=service))
    event = context.message.model_copy(update={"text": "private input" if kind != "empty" else None})
    flags = {"mask_logged_message": kind == "masked"}
    data = {
        "event_chat": event.chat,
        "event_from_user": event.from_user,
        "handler": SimpleNamespace(flags=flags),
        CONTAINER_NAME: request,
    }
    expected = "private input"
    if kind == "caption":
        event = event.model_copy(update={"text": None, "caption": "photo caption"})
        expected = "photo caption"
    elif kind == "masked":
        expected = "[masked]"
    elif kind == "callback":
        event = context.callback.model_copy(update={"data": "settings:back_to_settings"})
    elif kind == "no_chat":
        data.pop("event_chat")
    elif kind == "no_user":
        data.pop("event_from_user")
    elif kind == "empty":
        expected = None

    async def handler(received, payload):
        assert received is event and payload is data
        assert len(session.new) == (0 if kind in {"no_chat", "no_user"} else 1)
        return "handled"

    assert await ActionLogMiddleware()(handler, event, data) == "handled"
    if kind in {"no_chat", "no_user"}:
        request.get.assert_not_awaited()
        return
    [row] = list(session.new)
    assert isinstance(row, ActionLog) and isinstance(row.id, uuid.UUID)
    assert row.chat_id == 974001 and row.user_id == 974001
    assert row.message_text == (None if kind == "callback" else expected)
    assert row.callback_query_data == ("settings:back_to_settings" if kind == "callback" else None)
    await session.flush()
    assert await session.get(ActionLog, row.id) is row


@pytest.mark.parametrize("callback", [False, True])
async def test_private_chat_guard_prevents_audit_and_handler(context, callback):
    group = Chat(id=-974001, type="supergroup")
    message = context.message.model_copy(update={"chat": group})
    event = context.callback.model_copy(update={"message": message}) if callback else message
    request = SimpleNamespace(get=AsyncMock())
    data = {
        "event_chat": group,
        "event_from_user": context.message.from_user,
        "handler": SimpleNamespace(flags={"private_chat_only": True}),
        CONTAINER_NAME: request,
    }
    handler = AsyncMock()

    async def audit(received, payload):
        return await ActionLogMiddleware()(handler, received, payload)

    assert await PrivateChatOnlyMiddleware()(audit, event, data) is None
    request.get.assert_not_awaited()
    handler.assert_not_awaited()
    [sent] = [call.args[1] for call in context.request.await_args_list]
    assert sent.text == catalog.i18n.gettext("common.private_chat_only")
    if callback:
        assert sent.show_alert is True


@pytest.mark.parametrize("chat_type", [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL])
@pytest.mark.parametrize("kind", ["message", "masked", "callback"])
async def test_audit_only_persists_private_chat_updates(context, chat_type, kind):
    chat = Chat(id=974001 if chat_type == ChatType.PRIVATE else -974001, type=chat_type)
    message = context.message.model_copy(update={"chat": chat, "text": "private input"})
    event = (
        context.callback.model_copy(update={"message": message, "data": "settings:back_to_settings"})
        if kind == "callback"
        else message
    )
    async with AsyncSession() as session:
        service = ActionLogService(ActionLogRepository(session))
        request = SimpleNamespace(get=AsyncMock(return_value=service))
        data = {
            "event_chat": chat,
            "event_from_user": message.from_user,
            "handler": SimpleNamespace(flags={"mask_logged_message": kind == "masked"}),
            CONTAINER_NAME: request,
        }

        async def handler(received, payload):
            assert received is event and payload is data
            assert len(session.new) == int(chat_type == ChatType.PRIVATE)
            return "handled"

        assert await ActionLogMiddleware()(handler, event, data) == "handled"
        if chat_type != ChatType.PRIVATE:
            request.get.assert_not_awaited()
            return
        request.get.assert_awaited_once_with(ActionLogService)
        [row] = list(session.new)
        assert row.chat_id == chat.id and row.user_id == message.from_user.id
        assert row.callback_query_data == (event.data if kind == "callback" else None)
        assert row.message_text == {"message": "private input", "masked": "[masked]", "callback": None}[kind]


async def test_per_chat_ordering_serializes_one_chat_and_allows_another():
    middleware = PerChatOrderingMiddleware()
    entered, release, attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    trace = []

    async def handler(event, data):
        trace.append((event, "enter"))
        if event == "first":
            entered.set()
            await release.wait()
        trace.append((event, "exit"))
        return event

    async def second():
        attempted.set()
        return await middleware(handler, "second", {"event_chat": SimpleNamespace(id=1)})

    async with asyncio.TaskGroup() as tasks:
        first = tasks.create_task(middleware(handler, "first", {"event_chat": SimpleNamespace(id=1)}))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            following = tasks.create_task(second())
            await asyncio.wait_for(attempted.wait(), 1)
            assert await middleware(handler, "other", {"event_chat": SimpleNamespace(id=2)}) == "other"
            assert ("second", "enter") not in trace
        finally:
            release.set()
    assert first.result() == "first" and following.result() == "second"
    assert trace.index(("first", "exit")) < trace.index(("second", "enter"))


def load_runtime_module(source, runtime):
    relative = Path(source.__file__).relative_to(Path(manashelper.__file__).parent)
    target = runtime / "src" / "manashelper" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.__file__, target)
    spec = importlib.util.spec_from_file_location("runtime_platform", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_command_catalog_keeps_runtime_path_and_reads_changes_without_restart(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    shutil.copytree(command_catalog.COMMANDS_DIR, runtime / "docs" / "commands")
    monkeypatch.chdir(tmp_path)
    module = load_runtime_module(command_catalog, runtime)
    assert runtime / "docs" / "commands" == module.COMMANDS_DIR
    assert module.build_private_commands(catalog.Locale.EN)
    (module.COMMANDS_DIR / "private.json").write_text('[{"command":"start","description":"commands.start"}]')
    assert [command.command for command in module.build_private_commands(catalog.Locale.EN)] == ["start"]


def test_gettext_keeps_runtime_locales_path_after_relocation(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    shutil.copytree(Path(manashelper.__file__).parent / "locales", runtime / "src" / "manashelper" / "locales")
    monkeypatch.chdir(tmp_path)
    module = load_runtime_module(catalog, runtime)
    assert Path(module.i18n.path) == runtime / "src" / "manashelper" / "locales"
    assert module.i18n.gettext("common.welcome", locale="en") == "Welcome to Manashelper!"


async def test_platform_provider_keeps_request_scope_and_global_model_registry():

    assert Base.metadata.tables["action_logs"] is ActionLog.__table__
    dependencies = (ActionLogService, ActionLogRepository)
    async with make_async_container(CoreProvider(), TelegramPlatformProvider()) as container:
        async with container() as request:
            first = [await request.get(dependency) for dependency in dependencies]
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is await request.get(dependency)
        async with container() as request:
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is not await request.get(dependency)


def test_scheduler_has_no_scheduled_message_deletion_job():
    scheduler = create_scheduler("container", "bot")
    assert all(job.func.__name__ != "cleanup_scheduled_message_deletions_job" for job in scheduler.get_jobs())
