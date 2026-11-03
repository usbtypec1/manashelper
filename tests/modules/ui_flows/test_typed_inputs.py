from unittest.mock import AsyncMock

import pytest_asyncio
from aiogram import Bot
from aiogram.methods import DeleteMessage, SendMessage
from aiogram.types import Chat, Contact, Message, PhotoSize, Update, User
from sqlalchemy import func, select

from manashelper.core.config import get_settings
from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation, UiInputSecret
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiScreenDelivery
from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.secrets import SecretCodec
from manashelper.platform.telegram.audit.orm import ActionLog
from tests.modules.ui_flows.telegram_factory import TelegramHarness, container_for, dispatcher_for
from tests.modules.ui_flows.test_effect_worker import external_document, external_override
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import DelegateResult
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import RuntimeUser


def text(value):
    return {"kind": "inline", "translations": {"en": value}}


@pytest_asyncio.fixture
async def typed_harness(isolated_flow_pool, monkeypatch):
    user_id = 991790
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(user_id))
    get_settings.cache_clear()
    calls = []

    async def external(context, arguments):
        calls.append(context.event_id)
        assert context.secrets == {"password": "private-secret"}
        assert any(isinstance(method, DeleteMessage) for method in harness.calls)
        return DelegateResult("success", {"reply": "Verified once"})

    try:
        async with (
            Bot(token="123456:synthetic-typed-input") as bot,
            container_for(isolated_flow_pool, external_override(external)) as container,
        ):
            harness = TelegramHarness(bot, dispatcher_for(container, user_id, ingress=True), user_id)
            monkeypatch.setattr(bot.session, "make_request", harness.respond)
            monkeypatch.setattr(bot, "me", AsyncMock(side_effect=AssertionError("Password requested bot identity")))
            await (await container.get(FlowTelegramCoordinator)).install_defaults(user_id)
            yield harness, container, isolated_flow_pool, calls
            await harness.dispatcher.storage.close()
    finally:
        get_settings.cache_clear()


async def publish(container, document, user_id):
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        await flows.create(document)
        await flows.publish(document.id, 0, user_id)


async def active(harness, container):
    async with container() as request:
        return await (await request.get(DialogService)).active(RuntimeUser(harness.user_id, harness.user_id))


async def feed(harness, update_id, **payload):
    await harness.dispatcher.feed_update(
        harness.bot,
        Update(
            update_id=update_id,
            message=Message(
                message_id=payload.pop("message_id", update_id),
                date=0,
                chat=Chat(id=harness.user_id, type="private"),
                from_user=User(id=harness.user_id, is_bot=False, first_name="Typed input", language_code="en"),
                **payload,
            ),
        ),
    )


async def test_unified_secret_input_is_deleted_encrypted_masked_and_completed_once(typed_harness):
    harness, container, pool, calls = typed_harness
    document = external_document().model_dump(mode="json")
    document["entry"], document["inputs"] = "password", {}
    document["nodes"].insert(
        0,
        {
            "kind": "input",
            "id": "password",
            "field": "password",
            "input_type": "secret",
            "next": "fetch",
            "text": [text("Enter secret")],
            "error": text("Invalid secret"),
        },
    )
    await publish(container, FlowDocument.model_validate(document), harness.user_id)
    await harness.message("/flow_demo external_worker", 179001)
    await harness.message("/unknown", 179099)
    assert (await active(harness, container)).node_id == "password"
    await harness.message("private-secret", 179002)
    harness.bot.me.assert_not_awaited()
    waiting = await active(harness, container)
    assert waiting.status == "waiting_effect" and waiting.node_id == "fetch" and not calls
    async with pool() as session:
        operation = await session.scalar(select(UiExternalOperation))
        saved_secret = await session.scalar(select(UiInputSecret))
        assert operation.status == "pending"
        assert operation.arguments["password"] == str(saved_secret.id)
        codec = await container.get(SecretCodec)
        assert (
            codec.decrypt(saved_secret.ciphertext, saved_secret.id, waiting.id, harness.user_id, harness.user_id)
            == "private-secret"
        )
        audit = await session.scalar(select(ActionLog.message_text).where(ActionLog.message_text == "private-secret"))
        assert audit is None
        assert "[masked]" in list(await session.scalars(select(ActionLog.message_text)))
        stored = []
        for model, columns in (
            (UiDialogSession, (UiDialogSession.data, UiDialogSession.frames)),
            (UiIngressReceipt, (UiIngressReceipt.decision,)),
            (UiScreenDelivery, (UiScreenDelivery.screen,)),
            (UiExternalOperation, (UiExternalOperation.arguments, UiExternalOperation.result)),
        ):
            stored.extend((await session.execute(select(*columns).select_from(model))).all())
        assert "private-secret" not in str(stored) + saved_secret.ciphertext
        operation_id = operation.id
    worker = await container.get(EffectWorker)
    succeeded = await worker.run(operation_id)
    assert succeeded.status == "succeeded" and len(calls) == 1
    coordinator = await container.get(FlowTelegramCoordinator)
    await coordinator.complete_effect(harness.bot, operation_id)
    ready = await active(harness, container)
    assert ready.node_id == "ready" and ready.data["answer"] == "Verified once"
    delivered = sum(isinstance(method, SendMessage) and method.text == "Verified once" for method in harness.calls)
    assert delivered == 1
    count = len(harness.calls)
    await coordinator.complete_effect(harness.bot, operation_id)
    await harness.message("private-secret", 179002)
    assert len(harness.calls) == count and len(calls) == 1
    async with pool() as session:
        assert (await session.get(UiExternalOperation, operation_id)).status == "applied"
        assert await session.scalar(select(func.count()).select_from(UiInputSecret)) == 0
        assert (
            await session.scalar(select(func.count()).select_from(UiFlowEvent).where(UiFlowEvent.update_id == 179002))
            == 1
        )


def input_document(input_type, field):
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "typed_" + input_type,
            "entry": "collect",
            "fields": {"value": field},
            "nodes": [
                {
                    "kind": "input",
                    "id": "collect",
                    "field": "value",
                    "input_type": input_type,
                    "multiple": input_type == "media",
                    "next": "ready",
                    "text": [text("Provide input")],
                    "error": text("Invalid input"),
                    "buttons": [[{"kind": "transition", "id": "done", "target": "ready", "label": text("Done")}]],
                },
                {"kind": "menu", "id": "ready", "keyboard": "inline", "text": [text("Accepted")], "buttons": []},
            ],
        }
    )


async def test_contact_owner_mismatch_preserves_wait_and_owner_contact_is_accepted(typed_harness):
    harness, container, _, _ = typed_harness
    document = input_document("contact", {"type": "text"})
    await publish(container, document, harness.user_id)
    await harness.message("/flow_demo typed_contact", 179010)
    before = await active(harness, container)
    await feed(
        harness, 179011, contact=Contact(phone_number="+996555000001", first_name="Other", user_id=harness.user_id + 1)
    )
    rejected = await active(harness, container)
    assert rejected.id == before.id and rejected.revision == before.revision and rejected.data == {}
    await feed(
        harness, 179012, contact=Contact(phone_number="+996555000002", first_name="Owner", user_id=harness.user_id)
    )
    accepted = await active(harness, container)
    assert accepted.node_id == "ready" and accepted.data == {"value": "+996555000002"}


async def test_media_collection_deduplicates_message_ids_preserves_payloads_and_caps_ten(typed_harness):
    harness, container, _, _ = typed_harness
    item = {
        "type": "object",
        "properties": {
            "message_id": {"type": "integer"},
            "type": {"type": "text"},
            "file_id": {"type": "text"},
            "media_group_id": {"type": "text", "nullable": True},
            "caption": {"type": "text", "nullable": True},
        },
    }
    await publish(container, input_document("media", {"type": "list", "items": item, "max_items": 10}), harness.user_id)
    await harness.message("/flow_demo typed_media", 179020)
    for index in range(10):
        await feed(
            harness,
            179021 + index,
            photo=[PhotoSize(file_id=f"saved-{index}", file_unique_id=f"unique-{index}", width=10, height=10)],
            media_group_id="album",
            caption=f"Caption <{index}>",
        )
    collected = await active(harness, container)
    assert len(collected.data["value"]) == 10 and collected.node_id == "collect"
    await feed(
        harness,
        179040,
        message_id=179021,
        photo=[PhotoSize(file_id="replacement", file_unique_id="replacement", width=10, height=10)],
        caption="Must not replace",
    )
    assert (await active(harness, container)).data == collected.data
    await feed(harness, 179041, photo=[PhotoSize(file_id="overflow", file_unique_id="overflow", width=10, height=10)])
    assert (await active(harness, container)).data == collected.data
    assert collected.data["value"][0] == {
        "message_id": 179021,
        "type": "photo",
        "file_id": "saved-0",
        "media_group_id": "album",
        "caption": "Caption <0>",
    }
    await harness.message("Done", 179042)
    assert (await active(harness, container)).data == collected.data
