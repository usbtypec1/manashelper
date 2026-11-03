import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from aiogram import Bot
from aiogram.methods import SendMessage
from dishka import Provider, Scope, provide
from sqlalchemy import func, select

from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiScreenDelivery, UiUserTransition
from manashelper.modules.ui_flows.presentation.admin_contracts import PreviewDelegateResult, PreviewRequest, PreviewUser
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.preview import preview
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.secrets import SecretCodec, SecretUnavailableError
from tests.modules.ui_flows.telegram_factory import TelegramHarness, container_for
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry, ExternalDelegateRegistry
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import DelegateDefinition, DelegateResult
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import RuntimeUser


def external_definition():
    return DelegateDefinition.model_validate(
        {
            "id": "test.external",
            "effect": "external",
            "inputs": {"password": {"type": "secret"}, "request": {"type": "text"}},
            "outputs": {"reply": {"type": "text"}},
            "outcomes": ["success"],
        }
    )


def external_document():
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "external_worker",
            "entry": "fetch",
            "fields": {"password": {"type": "secret"}, "answer": {"type": "text", "nullable": True}},
            "inputs": {"password": {"type": "secret"}},
            "initial_data": {"answer": None},
            "nodes": [
                {
                    "kind": "action",
                    "id": "fetch",
                    "delegate": "test.external",
                    "arguments": {
                        "password": {"kind": "ref", "scope": "data", "field": "password"},
                        "request": {"kind": "literal", "value": "checked-request"},
                    },
                    "results": {"reply": "answer"},
                    "outcomes": {"success": "ready"},
                    "waiting_text": [{"kind": "inline", "translations": {"en": "Please wait"}}],
                },
                {
                    "kind": "menu",
                    "id": "ready",
                    "keyboard": "inline",
                    "text": [
                        {
                            "kind": "inline",
                            "translations": {"en": "{answer}"},
                            "parameters": {"answer": {"kind": "ref", "scope": "data", "field": "answer"}},
                        }
                    ],
                    "buttons": [
                        [
                            {
                                "kind": "transition",
                                "id": "finish",
                                "target": "done",
                                "label": {"kind": "inline", "translations": {"en": "Done"}},
                            }
                        ]
                    ],
                },
                {"kind": "end", "id": "done", "status": "completed", "text": []},
            ],
        }
    )


def external_override(handler):
    registry = ExternalDelegateRegistry([DelegateBinding(external_definition(), handler)])

    class External(Provider):
        @provide(scope=Scope.APP, override=True)
        def external_registry(self) -> ExternalDelegateRegistry:
            return registry

    return External()


async def prepare(container, pool):
    user = RuntimeUser(991_781, 991_781)
    secret_id = uuid4()
    async with pool.begin() as session:
        session.add(User(id=user.id, full_name="External worker test", locale="en"))
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        document = external_document()
        await flows.create(document)
        await flows.publish(document.id, 0, user.id)
        result = await (await request.get(DialogService)).start(
            document.id, user, 7810, arguments={"password": str(secret_id)}
        )
        codec = await container.get(SecretCodec)
        ciphertext = codec.encrypt("never-store-this-password", secret_id, result.state.id, user.id, user.chat_id)
        await (await request.get(EffectRepository)).put_secret(
            secret_id, result.state.id, user.id, user.chat_id, ciphertext, datetime.now(UTC) + timedelta(minutes=5)
        )
    async with pool() as observer:
        operation = await observer.scalar(select(UiExternalOperation))
        state = await observer.get(UiDialogSession, result.state.id)
        assert operation.status == "pending" and state.status == "waiting_effect"
        assert "never-store-this-password" not in str(operation.arguments) + str(state.data) + ciphertext
        operation_id = operation.id
    return user, result.state, secret_id, operation_id


async def test_worker_commits_unknown_releases_chat_lock_decrypts_owner_and_applies_saved_result_once(
    isolated_flow_pool,
):
    pool = isolated_flow_pool
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        assert context.secrets == {"password": "never-store-this-password"}
        assert "never-store-this-password" not in repr(context)
        assert arguments["request"] == "checked-request"
        assert arguments["password"] != context.secrets["password"]
        async with pool.begin() as observer:
            operation = await observer.get(UiExternalOperation, operation_id)
            assert operation.status == "unknown"
            assert await observer.scalar(select(func.pg_try_advisory_xact_lock(context.chat_id))) is True
        return DelegateResult("success", {"reply": "Saved external result"})

    async with container_for(pool, external_override(external)) as container:
        user, state, secret_id, operation_id = await prepare(container, pool)
        worker = await container.get(EffectWorker)
        async with pool() as observer:
            secret = await observer.get(UiInputSecret, secret_id)
            codec = await container.get(SecretCodec)
            with pytest.raises(SecretUnavailableError):
                codec.decrypt(secret.ciphertext, secret_id, state.id, user.id + 1, user.chat_id)
        saved = await worker.run(operation_id)
        assert saved.status == "succeeded" and saved.result.values == {"reply": "Saved external result"}
        assert (await worker.run(operation_id)).result == saved.result
        assert calls == [str(operation_id)]
        # A fresh REQUEST applies the saved result without another external call.
        async with catalog_request(container) as request:
            result = await (await request.get(DialogService)).apply_effect(operation_id, user)
            assert result.state.status == "waiting_button" and result.state.node_id == "ready"
            assert (
                result.state.data["answer"] == "Saved external result" and result.state.revision == state.revision + 1
            )
        async with catalog_request(container) as request:
            assert await (await request.get(DialogService)).apply_effect(operation_id, user) is None
        async with pool() as observer:
            assert (await observer.get(UiExternalOperation, operation_id)).status == "applied"
            assert await observer.get(UiInputSecret, secret_id) is None
            assert (
                await observer.scalar(
                    select(func.count())
                    .select_from(UiUserTransition)
                    .where(UiUserTransition.operation_id == operation_id)
                )
                == 1
            )
        assert await worker.run(operation_id) is None and calls == [str(operation_id)]


async def test_cancelled_external_attempt_remains_unknown_and_is_never_automatically_retried(isolated_flow_pool):
    started = asyncio.Event()
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        started.set()
        await asyncio.Event().wait()

    async with container_for(isolated_flow_pool, external_override(external)) as container:
        user, state, secret_id, operation_id = await prepare(container, isolated_flow_pool)
        worker = await container.get(EffectWorker)
        task = asyncio.create_task(worker.run(operation_id))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with isolated_flow_pool() as observer:
            operation = await observer.get(UiExternalOperation, operation_id)
            assert operation.status == "unknown" and operation.result is None
            assert operation_id not in await EffectRepository(observer).pending()
        assert await worker.run(operation_id) is None and calls == [str(operation_id)]


async def test_saved_external_result_cannot_reopen_a_cancelled_execution(isolated_flow_pool):
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        return DelegateResult("success", {"reply": "Late result"})

    async with container_for(isolated_flow_pool, external_override(external)) as container:
        user, state, secret_id, operation_id = await prepare(container, isolated_flow_pool)
        worker = await container.get(EffectWorker)
        assert (await worker.run(operation_id)).status == "succeeded"
        async with catalog_request(container) as request:
            await (await request.get(DialogService)).cancel_active(user, 7811)
        async with catalog_request(container) as request:
            assert await (await request.get(DialogService)).apply_effect(operation_id, user) is None
            assert await (await request.get(DialogService)).active(user) is None
            cancelled = await (await request.get(DialogService)).get(state.id, user)
            assert cancelled.status == "cancelled" and cancelled.data["answer"] is None
        assert await worker.run(operation_id) is None and calls == [str(operation_id)]


async def test_restart_recovers_a_committed_effect_screen_before_its_first_delivery_claim(
    isolated_flow_pool, monkeypatch
):
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        return DelegateResult("success", {"reply": "Recovered screen"})

    async with (
        container_for(isolated_flow_pool, external_override(external)) as container,
        Bot(token="123456:synthetic-effect-recovery") as bot,
    ):
        user, state, secret_id, operation_id = await prepare(container, isolated_flow_pool)
        worker = await container.get(EffectWorker)
        assert (await worker.run(operation_id)).status == "succeeded"
        coordinator = await container.get(FlowTelegramCoordinator)
        # Model process loss after apply+screen intent commit, before claim or Telegram I/O.
        with monkeypatch.context() as patch:
            patch.setattr(coordinator, "_deliver", AsyncMock(side_effect=asyncio.CancelledError))
            with pytest.raises(asyncio.CancelledError):
                await coordinator.complete_effect(bot, operation_id)
        async with isolated_flow_pool() as observer:
            operation = await observer.get(UiExternalOperation, operation_id)
            intent = await observer.scalar(
                select(UiScreenDelivery).where(UiScreenDelivery.operation_id == operation_id)
            )
            assert operation.status == "applied" and intent.status == "pending"
            assert operation_id in await EffectRepository(observer).pending()
            token = intent.token
        recovered_worker = EffectWorker(
            container, await container.get(ExternalDelegateRegistry), await container.get(SecretCodec)
        )
        assert (await recovered_worker.run(operation_id)).status == "applied"
        transport = TelegramHarness(bot, None, user.id)
        monkeypatch.setattr(bot.session, "make_request", transport.respond)
        await coordinator.complete_effect(bot, operation_id)
        count = len(transport.calls)
        assert count == 2 and all(isinstance(method, SendMessage) for method in transport.calls)
        assert transport.calls[0].text == "Recovered screen"
        await coordinator.complete_effect(bot, operation_id)
        assert len(transport.calls) == count and await recovered_worker.run(operation_id) is None
        async with isolated_flow_pool() as observer:
            assert (await observer.get(UiScreenDelivery, token)).status == "sent"
            assert operation_id not in await EffectRepository(observer).pending()
            assert await observer.scalar(select(func.count()).select_from(UiScreenDelivery)) == 1
        assert calls == [str(operation_id)]


async def test_external_preview_requires_explicit_stub_and_never_runs_live_handler():
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        raise AssertionError("Preview must not execute an external handler")

    registry = DelegateRegistry([DelegateBinding(external_definition(), external)])
    body = PreviewRequest(
        document=external_document(),
        user=PreviewUser(id=1, chat_id=1, locale="en", theme="basic"),
        eders_enabled=False,
        data={"password": str(uuid4())},
        delegate_results={
            "test.external": PreviewDelegateResult(outcome="success", values={"reply": "Stubbed output"})
        },
    )
    result = await preview(body, registry, FlowPolicy())
    assert result.issues == [] and result.node_id == "ready" and result.screen.text == "Stubbed output"
    missing = await preview(body.model_copy(update={"delegate_results": {}}), registry, FlowPolicy())
    assert missing.issues and calls == []


async def test_effect_delivery_and_navigation_share_the_update_chat_gate(isolated_flow_pool, monkeypatch):
    from aiogram.types import Chat, Message

    from manashelper.platform.telegram.middlewares.per_chat_ordering import PerChatOrderingMiddleware

    async def external(context, arguments):
        return DelegateResult("success", {"reply": "Old effect screen"})

    async with (
        container_for(isolated_flow_pool, external_override(external)) as container,
        Bot(token="123456:synthetic-effect-ordering") as bot,
    ):
        user, state, secret_id, operation_id = await prepare(container, isolated_flow_pool)
        assert (await (await container.get(EffectWorker)).run(operation_id)).status == "succeeded"
        paused, release, navigated = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def pause_old_screen(method):
            if isinstance(method, SendMessage) and method.text == "Old effect screen":
                paused.set()
                await release.wait()

        transport = TelegramHarness(bot, None, user.id, network_hook=pause_old_screen)
        monkeypatch.setattr(bot.session, "make_request", transport.respond)
        coordinator = await container.get(FlowTelegramCoordinator)
        effect = asyncio.create_task(coordinator.complete_effect(bot, operation_id))
        await asyncio.wait_for(paused.wait(), 5)

        async def navigate(event, data):
            navigated.set()
            async with catalog_request(container) as request:
                await (await request.get(DialogService)).cancel_active(user, 7812)
            await bot.send_message(user.chat_id, "New menu")

        message = Message(message_id=7812, date=0, chat=Chat(id=user.chat_id, type="private"))
        # The same APP gate is resolved by separately constructed observer middleware.
        middleware = PerChatOrderingMiddleware(container)
        navigation = asyncio.create_task(middleware(navigate, message, {"event_chat": message.chat}))
        try:
            await asyncio.sleep(0.02)
            assert not navigated.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(effect, navigation), 5)
        assert [method.text for method in transport.calls if isinstance(method, SendMessage)][-1] == "New menu"
        async with catalog_request(container) as request:
            assert await (await request.get(DialogService)).active(user) is None
