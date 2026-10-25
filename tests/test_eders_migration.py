from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from dishka import make_async_container
from sqlalchemy.dialects import postgresql
from test_eders_tracking import NOW, item

from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.db.models import User
from manashelper.localization.locale import Locale
from manashelper.modules.eders.application.eders import EdersService
from manashelper.modules.eders.application.models import DeadlineFilter, EdersSnapshot
from manashelper.modules.eders.application.polling import PollEdersUser
from manashelper.modules.eders.application.tracking import EdersEvent, EdersSetting, EdersTrackingService
from manashelper.modules.eders.infrastructure.client import EdersClient
from manashelper.modules.eders.infrastructure.orm import EdersState
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.eders.infrastructure.serialization import deserialize_snapshot, serialize_snapshot
from manashelper.modules.eders.jobs import poll_eders_job
from manashelper.modules.eders.presentation.callbacks import EdersPageCallback, EdersSettingCallback
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.obis.errors import UserNotFoundError
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.i18n.catalog import i18n


async def test_first_state_locks_user_before_loading_and_flushes_defaults():
    calls = []
    session = AsyncMock()
    session.add = Mock(side_effect=lambda row: calls.append("add"))
    session.get.side_effect = lambda *args, **kwargs: calls.append("get")
    session.execute.side_effect = lambda query: calls.append("lock")
    session.flush.side_effect = lambda: calls.append("flush")
    state = await EdersRepository(session).get_state(42)
    assert calls == ["lock", "get", "add", "flush"]
    query = session.execute.call_args.args[0]
    assert str(query.compile(dialect=postgresql.dialect())) == (
        "SELECT users.id \nFROM users \nWHERE users.id = %(id_1)s FOR UPDATE"
    )
    assert query.compile().params == {"id_1": 42}
    session.get.assert_awaited_once_with(EdersState, 42, populate_existing=True)
    assert state.user_id == 42


async def test_existing_state_is_reloaded_under_lock_without_flush():
    state = EdersState(user_id=42)
    session = AsyncMock()
    session.get.return_value = state
    session.add = Mock()
    assert await EdersRepository(session).get_state(42) is state
    session.execute.assert_awaited_once()
    session.flush.assert_not_awaited()
    session.add.assert_not_called()


def test_snapshot_persistence_format_and_legacy_defaults_are_stable():
    now = datetime(2026, 10, 1, tzinfo=UTC)
    payload = '{"activities": [], "fetched_at": "2026-10-01T00:00:00+00:00", "courses": [], "schema_version": 2}'
    assert serialize_snapshot(EdersSnapshot((), now)) == payload
    legacy = deserialize_snapshot('{"activities": [], "fetched_at": "2026-10-01T00:00:00+00:00"}')
    assert legacy == EdersSnapshot((), now, schema_version=1)
    assert deserialize_snapshot(payload) == EdersSnapshot((), now)


@pytest.mark.parametrize("selected", list(DeadlineFilter))
def test_page_callback_payload_stays_compatible(selected):
    assert EdersPageCallback(selected=selected, page=7).pack() == f"eders:{selected.value}:7"


@pytest.mark.parametrize("setting", list(EdersSetting))
def test_setting_callback_payload_stays_compatible(setting):
    assert EdersSettingCallback(setting=setting).pack() == f"eders_setting:{setting.value}"


@pytest.mark.parametrize("failure", ["refresh", "locale", "pending"])
async def test_poll_failure_aborts_only_current_user_and_preserves_call_order(failure):
    calls = []
    service, tracking, locales = AsyncMock(), AsyncMock(), AsyncMock()
    tracking.get_poll_user_ids.return_value = [1, 2]

    async def operation(name, user_id):
        calls.append((name, user_id))
        if name == failure and user_id == 1:
            raise RuntimeError("unexpected failure")
        return Locale.EN if name == "locale" else []

    async def refresh(user_id):
        return await operation("refresh", user_id)

    async def locale(user_id):
        return await operation("locale", user_id)

    async def pending(user_id, now):
        return await operation("pending", user_id)

    service.get_snapshot.side_effect = refresh
    locales.get_locale.side_effect = locale
    tracking.pending_events.side_effect = pending
    dependencies = {EdersTrackingService: tracking, PollEdersUser: PollEdersUser(service, tracking, locales)}
    scopes = []

    @asynccontextmanager
    async def container():
        scopes.append("enter")
        try:
            yield SimpleNamespace(get=AsyncMock(side_effect=lambda cls: dependencies[cls]))
        finally:
            scopes.append("exit")

    bot = AsyncMock()
    await poll_eders_job(container, bot)
    operations = ["refresh", "locale", "pending"]
    assert calls == [(name, 1) for name in operations[: operations.index(failure) + 1]] + [
        (name, 2) for name in operations
    ]
    assert scopes == ["enter", "exit"] * 3
    bot.send_message.assert_not_awaited()
    tracking.mark_sent.assert_not_awaited()


async def test_missing_user_is_rejected_before_state_creation():
    repository, users = AsyncMock(), AsyncMock()
    users.exists.return_value = False
    with pytest.raises(UserNotFoundError):
        await EdersTrackingService(repository, users).get_settings(42)
    users.exists.assert_awaited_once_with(42)
    repository.get_state.assert_not_awaited()


async def test_poll_eligibility_requires_both_credential_columns(session):
    users = [
        User(id=976701, full_name="none"),
        User(id=976702, full_name="number", student_number="fixture"),
        User(id=976703, full_name="password", encrypted_password="fixture"),
        User(id=976704, full_name="both", student_number="fixture", encrypted_password="fixture"),
    ]
    session.add_all(users)
    await session.flush()
    selected = await EdersRepository(session).get_poll_user_ids()
    assert set(selected) & {user.id for user in users} == {976704}


@pytest.mark.parametrize("failure", ["telegram", "unexpected", "ack"])
async def test_delivery_acknowledges_success_immediately_and_preserves_failure_boundary(failure):
    service, tracking, locales, bot = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    events = [
        EdersEvent("material-1", item(), "material_new", NOW, NOW),
        EdersEvent("material-2", item(), "material_changed", NOW, NOW),
        EdersEvent("reminder-1", item(), "before_24", NOW, NOW),
        EdersEvent("reminder-2", item(), "before_2", NOW, NOW),
    ]
    tracking.pending_events.return_value = events
    locales.get_locale.return_value = Locale.ZH
    calls = []

    async def send(*args, **kwargs):
        calls.append("send")
        assert kwargs["link_preview_options"].is_disabled is True
        if calls.count("send") == 2:
            if failure == "telegram":
                raise TelegramBadRequest(SendMessage(chat_id=42, text="fixture"), "gone")
            raise RuntimeError("transport failed")

    async def ack(user_id, key, now):
        assert user_id == 42 and now.tzinfo is UTC
        calls.append(key)
        if failure == "ack":
            raise RuntimeError("ack failed")

    bot.send_message.side_effect = send
    tracking.mark_sent.side_effect = ack
    poll = PollEdersUser(service, tracking, locales)
    with i18n.context(), i18n.use_locale("ru"):
        if failure == "telegram":
            await poll.execute(42, TelegramEdersNotificationSender(bot))
            assert calls == ["send", "material-1", "material-2", "send", "send", "reminder-2"]
        else:
            with pytest.raises(RuntimeError, match="ack failed" if failure == "ack" else "transport failed"):
                await poll.execute(42, TelegramEdersNotificationSender(bot))
            assert calls == (
                ["send", "material-1"] if failure == "ack" else ["send", "material-1", "material-2", "send"]
            )
        assert i18n.current_locale == "ru"
    assert "新增资料" in bot.send_message.await_args_list[0].args[1]


async def test_all_messages_are_formatted_before_any_delivery():
    bot = AsyncMock()
    events = [
        EdersEvent("valid", item(), "material_new", NOW, NOW),
        EdersEvent("invalid", item(), "unknown", NOW, NOW),
    ]
    with pytest.raises(KeyError):
        async for _event in TelegramEdersNotificationSender(bot).send(42, Locale.EN, events):
            pytest.fail("No event can be acknowledged before formatting completes")
    bot.send_message.assert_not_awaited()


async def test_eders_provider_keeps_app_request_scopes_and_model_registry():
    from manashelper.db.models import EdersNotification
    from manashelper.db.models import EdersState as RegisteredState
    from manashelper.modules.eders.infrastructure.orm import EdersNotification as OwnedNotification

    assert EdersState is RegisteredState
    assert EdersNotification is OwnedNotification
    assert Base.metadata.tables["eders_states"] is EdersState.__table__
    assert Base.metadata.tables["eders_notifications"] is EdersNotification.__table__
    dependencies = (EdersRepository, EdersService, EdersTrackingService, PollEdersUser)
    async with make_async_container(CoreProvider(), ObisProvider(), UsersProvider(), EdersProvider()) as container:
        client = await container.get(EdersClient)
        async with container() as request:
            first = [await request.get(dependency) for dependency in dependencies]
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is await request.get(dependency)
            assert client is await request.get(EdersClient)
        async with container() as request:
            for dependency, instance in zip(dependencies, first, strict=True):
                assert instance is not await request.get(dependency)
            assert client is await request.get(EdersClient)


async def test_recipient_load_failure_does_not_open_user_scope():
    tracking = AsyncMock()
    tracking.get_poll_user_ids.side_effect = RuntimeError("database unavailable")
    get = AsyncMock(return_value=tracking)

    @asynccontextmanager
    async def container():
        yield SimpleNamespace(get=get)

    bot = AsyncMock()
    await poll_eders_job(container, bot)
    get.assert_awaited_once_with(EdersTrackingService)
    bot.send_message.assert_not_awaited()
