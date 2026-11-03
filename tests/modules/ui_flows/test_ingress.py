import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, Chat, Message, User
from sqlalchemy import func, select

from manashelper.core.config import Settings
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.infrastructure.orm import UiScreenDelivery
from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt
from manashelper.modules.ui_flows.infrastructure.triggers import TriggerRepository
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.presentation.ingress_codecs import CODECS
from manashelper.modules.ui_flows.presentation.ingress_events import normalize
from manashelper.modules.ui_flows.triggers import trigger_document
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.telegram.audit.orm import ActionLog
from tests.modules.ui_flows.telegram_factory import dispatcher_for
from tests.modules.ui_flows.test_composition import child_document, parent_document
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.ingress import resolve
from ui_flows.domain.ingress import (
    ExpectedPosition,
    IncomingEvent,
    IngressContext,
    RouteDecision,
    ScenarioPin,
    TriggerBinding,
    TriggerManifest,
    TriggerRelease,
)
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import RuntimeUser
from ui_flows.errors import FlowConflictError, InvalidFlowError


def baseline():
    return TriggerRelease(
        1,
        0,
        1,
        datetime.now(UTC),
        TriggerManifest(
            document=trigger_document(),
            scenarios=[
                ScenarioPin(flow_id=flow, version=1, text_catalog_release=1)
                for flow in ("main_menu", "student_questions")
            ],
        ),
    )


def event(kind, key="", **values):
    return IncomingEvent(123456, 1, 10, 10, "private", kind, key=key, **values)


@pytest.mark.parametrize(
    "kind,key,extra,expected",
    [
        ("command", "start", {}, "launch"),
        ("deep_link", "student_questions", {}, "launch"),
        ("deep_link", "market", {}, "legacy"),
        ("deep_link", "ad_7bb4417d-fbb1-4f6a-8086-d9db5c9fe440", {}, "legacy"),
        ("deep_link", "ad_invalid", {}, "reject"),
        ("deep_link", "unknown", {}, "reject"),
        ("command", "unknown", {}, "reject"),
        ("command", "start", {"arguments": "not-a-root"}, "reject"),
        ("command", "broadcast", {}, "reject"),
        ("callback", "", {"codec": "uf"}, "runtime_callback"),
        ("callback", "", {"codec": "unknown", "valid": False}, "reject"),
    ],
)
def test_resolution_has_explicit_payloads_and_no_generic_start_or_form_fallthrough(kind, key, extra, expected):
    result = resolve(event(kind, key, **extra), baseline(), IngressContext(99, -99, rollout=True))
    assert result.kind == expected


def test_current_reply_wins_global_label_and_commands_cannot_be_answers():
    context = IngressContext(
        10,
        -99,
        runtime_flow="form",
        saved_reply=True,
        rollout=True,
        labels={"menu.settings": frozenset({"Same label"})},
    )
    assert resolve(event("text", text="Same label"), baseline(), context).kind == "runtime_text"
    assert resolve(event("command", "unknown"), baseline(), context).kind == "reject"
    assert resolve(event("command", "yemek"), baseline(), context).kind == "reject"
    assert resolve(event("command", "language"), baseline(), context).policy == "preserve"
    assert resolve(event("command", "start"), baseline(), context).policy == "replace"
    for kind in ("contact", "media"):
        assert resolve(event(kind), baseline(), context).kind == "reject"
    assert resolve(event("reply"), baseline(), context).adapter == "feedback"
    assert resolve(event("reply"), baseline(), replace(context, admin_id=99)).kind == "reject"


def test_group_moderation_and_legacy_form_ownership_are_explicit():
    context = IngressContext(10, -99, legacy_owner="obis", rollout=True)
    assert resolve(event("callback", codec="obis", action="cancel_credentials"), baseline(), context).adapter == "obis"
    assert resolve(event("callback", codec="phone_number_action", action="add"), baseline(), context).kind == "reject"
    assert resolve(event("contact", contact_owner=10, phone="private-contact"), baseline(), context).adapter == "obis"
    moderation = replace(
        event("callback", codec="ad_moderation", action="approve"), chat_type="supergroup", chat_id=-99
    )
    assert resolve(moderation, baseline(), IngressContext(10, -99)).adapter == "advertisement_moderation"
    assert resolve(replace(moderation, chat_id=-100), baseline(), IngressContext(10, -99)).kind == "reject"
    assert "private-contact" not in repr(event("contact", phone="private-contact"))


async def test_normalizer_uses_actor_checks_bot_mentions_and_validates_legacy_codecs():
    bot = Bot(token="123456:synthetic-test")
    bot.me = AsyncMock(return_value=User(id=bot.id, is_bot=True, first_name="Bot", username="correct_bot"))
    user = User(id=10, is_bot=False, first_name="Student")
    message = Message(
        message_id=1, date=0, chat=Chat(id=10, type="private"), from_user=user, text="/start@correct_bot market"
    )
    normalized = await normalize(message, bot, 1)
    assert normalized.kind == "deep_link" and normalized.key == "market" and normalized.valid
    wrong = await normalize(message.model_copy(update={"text": "/start@other_bot"}), bot, 2)
    assert not wrong.valid
    callback = CallbackQuery(
        id="query",
        from_user=user,
        chat_instance="chat",
        data="uf:token:0",
        message=message.model_copy(update={"from_user": User(id=bot.id, is_bot=True, first_name="Bot")}),
    )
    normalized = await normalize(callback, bot, 3)
    assert normalized.actor_id == 10 and normalized.codec == "uf" and normalized.valid
    bad = await normalize(callback.model_copy(update={"data": "course:not-an-integer"}), bot, 4)
    assert not bad.valid
    await bot.session.close()


async def test_password_normalization_keeps_unknown_slash_and_mention_as_opaque_text():
    bot = Bot(token="123456:synthetic-test")
    bot.me = AsyncMock(side_effect=AssertionError("A password must not trigger bot identity lookup"))
    message = Message(
        message_id=1,
        date=0,
        chat=Chat(id=10, type="private"),
        from_user=User(id=10, is_bot=False, first_name="Student"),
        text="/private@secret",
    )
    try:
        normalized = await normalize(message, bot, 1, known_commands=frozenset({"start"}))
        assert normalized.kind == "text" and normalized.text == message.text
        assert message.text not in repr(normalized)
        bot.me.assert_not_awaited()
    finally:
        await bot.session.close()


@pytest.mark.parametrize("password", ["/private@secret", "/broadcast@secret"])
async def test_legacy_password_accepts_unknown_and_inaccessible_commands_without_storing_secrets(
    ingress_flow, monkeypatch, password
):
    harness, container, pool = ingress_flow
    settings = await container.get(Settings)
    monkeypatch.setattr(settings, "admin_chat_id", harness.user_id + 1)
    save = AsyncMock()
    monkeypatch.setattr(ObisService, "save_credentials", save)
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, harness.user_id, harness.user_id))
    await memory.set_state("ObisCredentialsForm:password")
    await memory.set_data({"student_number": "synthetic-student"})
    await harness.message(password, 140120)
    save.assert_awaited_once_with(harness.user_id, "synthetic-student", password)
    assert await memory.get_state() is None
    async with pool() as session:
        receipt = await session.get(UiIngressReceipt, (harness.bot.id, 140120))
        assert receipt.decision["adapter"] == "obis" and password not in str(receipt.decision)
        assert list(await session.scalars(select(ActionLog.message_text))) == ["[masked]"]


@pytest_asyncio.fixture
async def ingress_flow(telegram_flow):
    harness, container, pool = telegram_flow
    await (await container.get(FlowTelegramCoordinator)).install_defaults(harness.user_id)
    harness.dispatcher = dispatcher_for(container, harness.user_id, ingress=True)
    return harness, container, pool


async def active(harness, container):
    async with container() as request:
        return await (await request.get(DialogService)).active(RuntimeUser(harness.user_id, harness.user_id))


async def test_dispatcher_commits_pinned_launch_then_delivers_and_deduplicates(ingress_flow):
    harness, container, pool = ingress_flow
    observed = []

    async def before_network(method):
        if isinstance(method, SendMessage):
            async with pool() as session:
                observed.append(await session.scalar(select(func.count()).select_from(UiIngressReceipt)))

    harness.network_hook = before_network
    await harness.message("/start", 140001)
    state = await active(harness, container)
    assert state.flow_id == "main_menu" and state.trigger_release == 1
    assert observed == [1]
    await harness.message("/start", 140001)
    assert len(harness.calls) == 1
    await harness.message("/hide_keyboard", 140002)
    await harness.message("/hide_keyboard", 140002)
    assert len(harness.calls) == 2
    assert (await active(harness, container)).id == state.id


async def test_busy_runtime_preserves_answers_rejects_commands_and_keeps_language(ingress_flow):
    harness, container, pool = ingress_flow
    await harness.message("/flow_demo", 140010)
    await harness.message("Open form", 140011)
    before = await active(harness, container)
    assert before.node_id == "answer"
    for index, text in enumerate(("/not_a_command", "/yemek", "/start ad_invalid", "/start market"), 140012):
        await harness.message(text, index)
        assert await active(harness, container) == before
    await harness.message("/language", 140016)
    child = await active(harness, container)
    assert child.id == before.id and child.flow_id == "select_locale"
    async with pool() as session:
        screen = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 140016))
    from manashelper.modules.ui_flows.presentation.callbacks import UiFlowCallback
    from ui_flows.domain.delivery import Screen

    buttons = [item for row in Screen.model_validate(screen.screen).buttons for item in row]
    index = next(index for index, item in enumerate(buttons) if item.id == "cancel")
    await harness.callback(UiFlowCallback(token=screen.token, index=index).pack(), screen.message_id, 140019)
    restored = await active(harness, container)
    assert restored.id == before.id and restored.node_id == before.node_id and restored.data == before.data
    await harness.message("private-answer", 140017)
    assert (await active(harness, container)).data["answer"] == "private-answer"
    async with pool() as session:
        receipts = list(await session.scalars(select(UiIngressReceipt.decision)))
        assert "private-answer" not in str(receipts)
        assert "not_a_command" not in str(receipts)
    await harness.message("/start", 140018)
    assert (await active(harness, container)).flow_id == "main_menu"


async def test_registry_pins_targets_and_retries_after_rollback_do_not_reactivate(ingress_flow):
    harness, container, pool = ingress_flow
    await harness.message("/start", 140030)
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        draft = await flows.get("main_menu")
        await flows.save(draft.document, draft.revision)
        await flows.publish("main_menu", 1, harness.user_id)
    # A graph publication cannot silently update the trigger manifest.
    await harness.message("/start", 140031)
    assert (await active(harness, container)).flow_version == 1
    async with catalog_request(container) as request:
        service = await request.get(TriggerService)
        draft = await service.draft()
        await service.save(draft.document, draft.revision)
        assert (await service.publish(1, harness.user_id)).id == 2
    await harness.message("/start", 140032)
    assert (await active(harness, container)).flow_version == 2
    async with catalog_request(container) as request:
        service = await request.get(TriggerService)
        await service.activate(1, 2)
        assert (await service.publish(1, harness.user_id)).id == 2
        assert (await service.current()).id == 1
        with pytest.raises(FlowConflictError):
            await service.activate(2, 2)
    await harness.message("/start", 140033)
    assert (await active(harness, container)).flow_version == 1


async def test_publication_rejects_ambiguous_bindings_and_unsafe_access_without_moving_release(ingress_flow):
    harness, container, _ = ingress_flow
    async with catalog_request(container) as request:
        service = await request.get(TriggerService)
        draft = await service.draft()
        copy = draft.document.bindings[0].model_copy(update={"id": "duplicate"})
        document = draft.document.model_copy(update={"bindings": [*draft.document.bindings, copy]})
        await service.save(document, 0)
        with pytest.raises(InvalidFlowError) as failure:
            await service.publish(1, harness.user_id)
        assert "ambiguous_binding" in {issue.code for issue in failure.value.issues}
        assert (await service.current()).id == 1
        admin = next(item for item in draft.document.bindings if item.id == "cmd_editor")
        unsafe = admin.model_copy(update={"access": "public"})
        document = draft.document.model_copy(
            update={"bindings": [unsafe if item.id == admin.id else item for item in draft.document.bindings]}
        )
        await service.save(document, 1)
        with pytest.raises(InvalidFlowError):
            await service.publish(2, harness.user_id)
        assert (await service.current()).id == 1


async def test_bootstrap_covers_all_registered_callback_codecs_and_preserves_operator_draft(ingress_flow):
    harness, container, _ = ingress_flow
    async with catalog_request(container) as request:
        service = await request.get(TriggerService)
        draft = await service.draft()
        assert {
            binding.matcher.key for binding in draft.document.bindings if binding.matcher.kind == "callback"
        } == set(CODECS)
        await service.save(draft.document, 0)
        await service.initialize(harness.user_id)
        assert (await service.draft()).revision == 1
        assert (await service.current()).draft_revision == 0


async def test_configured_typed_deep_link_launches_without_a_feature_handler_and_masks_receipts(ingress_flow):
    harness, container, pool = ingress_flow
    document = FlowDocument.model_validate(
        {
            "schema_version": 1,
            "id": "bound_target",
            "entry": "result",
            "fields": {"item": {"type": "text"}, "actor": {"type": "integer"}},
            "nodes": [
                {
                    "kind": "menu",
                    "id": "result",
                    "keyboard": "reply",
                    "buttons": [],
                    "text": [
                        {
                            "kind": "inline",
                            "translations": {"en": "Item {value}"},
                            "parameters": {"value": {"kind": "ref", "scope": "data", "field": "item"}},
                        }
                    ],
                }
            ],
        }
    )
    binding = TriggerBinding.model_validate(
        {
            "id": "item_link",
            "matcher": {"kind": "prefix", "key": "item_", "arguments": "uuid"},
            "target": {
                "kind": "scenario",
                "flow_id": "bound_target",
                "arguments": {"item": "argument", "actor": "actor_id"},
            },
        }
    )
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        await flows.create(document)
        await flows.publish(document.id, 0, harness.user_id)
        service = await request.get(TriggerService)
        draft = await service.draft()
        await service.save(draft.document.model_copy(update={"bindings": [*draft.document.bindings, binding]}), 0)
        await service.publish(1, harness.user_id)
    identifier = "7bb4417d-fbb1-4f6a-8086-d9db5c9fe440"
    await harness.message("/start item_" + identifier, 140040)
    state = await active(harness, container)
    assert state.flow_id == "bound_target" and state.trigger_release == 2
    assert state.data == {"item": identifier, "actor": harness.user_id}
    assert harness.calls[-1].text == "Item " + identifier
    async with pool() as session:
        assert identifier not in str(list(await session.scalars(select(UiIngressReceipt.decision))))


async def test_active_survey_returns_through_its_original_manifest_after_registry_changes(ingress_flow):
    harness, container, pool = ingress_flow
    await harness.message("/start student_questions", 140050)
    assert (await active(harness, container)).trigger_release == 1
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        draft = await flows.get("main_menu")
        await flows.save(draft.document, 0)
        await flows.publish("main_menu", 1, harness.user_id)
        service = await request.get(TriggerService)
        draft = await service.draft()
        await service.save(draft.document, 0)
        await service.publish(1, harness.user_id)
    for previous, current, button_id in ((140050, 140051, "year_1"), (140051, 140052, "no"), (140052, 140053, "yes")):
        async with pool() as session:
            delivery = await session.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == previous))
            buttons = [button for row in delivery.screen["buttons"] for button in row]
            index = [button["id"] for button in buttons].index(button_id)
        await harness.callback(f"uf:{delivery.token}:{index}", delivery.message_id, current)
    state = await active(harness, container)
    assert state.flow_id == "main_menu" and state.flow_version == 1 and state.trigger_release == 1
    count = len(harness.calls)
    await harness.callback(f"uf:{delivery.token}:{index}", delivery.message_id, current)
    assert len(harness.calls) == count + 1  # Only acknowledge the replay.


async def test_receipt_uniqueness_and_outer_rollback_do_not_copy_payloads(ingress_flow):
    harness, container, pool = ingress_flow
    incoming = IncomingEvent(
        harness.bot.id,
        140070,
        harness.user_id,
        harness.user_id,
        "private",
        "command",
        key="hide_keyboard",
        text="must-not-be-stored",
    )
    async with catalog_request(container) as request:
        release = await (await request.get(TriggerService)).current()
    decision = resolve(incoming, release, IngressContext(harness.user_id, -99))

    async def record():
        async with pool.begin() as session:
            return await TriggerRepository(session).record(incoming, decision)

    assert sorted(await asyncio.gather(record(), record())) == [False, True]
    with pytest.raises(RuntimeError):
        async with pool.begin() as session:
            await TriggerRepository(session).record(replace(incoming, update_id=140071), decision)
            raise RuntimeError("rollback receipt")
    async with pool() as session:
        rows = list(await session.scalars(select(UiIngressReceipt)))
        assert len(rows) == 1 and "must-not-be-stored" not in str(rows[0].decision)


async def test_study_entry_follows_scenario_navigation_after_node_rename(ingress_flow):
    harness, container, _ = ingress_flow
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        document = (await flows.get("main_menu")).document.model_dump(mode="json")
        document["navigation_entries"]["study"] = "academics"
        document["layout"]["academics"] = document["layout"].pop("study")
        for node in document["nodes"]:
            if node["id"] == "study":
                node["id"] = "academics"
            for row in node.get("buttons", []):
                for button in row:
                    if button.get("target") == "study":
                        button["target"] = "academics"
        await flows.save(FlowDocument.model_validate(document), 0)
        await flows.publish("main_menu", 1, harness.user_id)
        service = await request.get(TriggerService)
        draft = await service.draft()
        await service.save(draft.document, 0)
        await service.publish(1, harness.user_id)
    await harness.message(i18n.gettext("menu.study", locale="en"), 140080)
    state = await active(harness, container)
    assert state.flow_version == 2 and state.node_id == "academics"


async def test_completed_root_replay_cannot_clear_a_later_legacy_form(ingress_flow):
    harness, container, _ = ingress_flow
    await harness.message("/start", 140090)
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, harness.user_id, harness.user_id))
    await memory.set_state("PhoneNumberForm:phone_number")
    await memory.set_data({"keep": "private-local-draft"})
    before = len(harness.calls)
    await harness.message("/start", 140090)
    assert len(harness.calls) == before
    assert await memory.get_state() == "PhoneNumberForm:phone_number"
    assert await memory.get_data() == {"keep": "private-local-draft"}
    await harness.message("/start", 140091)
    assert await memory.get_state() is None


@pytest.mark.parametrize("move_to_root", [False, True])
async def test_pending_input_replay_requires_its_original_position(ingress_flow, move_to_root):
    harness, container, pool = ingress_flow
    await harness.message("/flow_demo", 140100)
    await harness.message("Open form", 140101)
    source = await active(harness, container)
    incoming = IncomingEvent(
        harness.bot.id, 140102, harness.user_id, harness.user_id, "private", "text", text="private-pending-answer"
    )
    decision = RouteDecision(
        kind="runtime_text",
        release_id=1,
        position=ExpectedPosition(session_id=str(source.id), revision=source.revision),
    )
    async with pool.begin() as session:
        await TriggerRepository(session).record(incoming, decision)
    if move_to_root:
        await harness.message("/start", 140103)
    await harness.message("private-pending-answer", 140102)
    following = await active(harness, container)
    if move_to_root:
        assert following.flow_id == "main_menu" and following.data == {}
    else:
        assert following.node_id == "confirm" and following.data["answer"] == "private-pending-answer"
        count = len(harness.calls)
        await harness.message("private-pending-answer", 140102)
        assert len(harness.calls) == count


async def test_pending_launch_replay_checks_position_and_current_admin_access(ingress_flow, monkeypatch):
    harness, container, pool = ingress_flow
    async with catalog_request(container) as request:
        service = await request.get(TriggerService)
        draft = await service.draft()
        binding = TriggerBinding.model_validate(
            {
                "id": "restricted",
                "matcher": {"kind": "command", "key": "restricted"},
                "target": {"kind": "scenario", "flow_id": "main_menu"},
                "access": "admin",
            }
        )
        await service.save(draft.document.model_copy(update={"bindings": [*draft.document.bindings, binding]}), 0)
        release = await service.publish(1, harness.user_id)
    incoming = IncomingEvent(
        harness.bot.id, 140110, harness.user_id, harness.user_id, "private", "command", key="restricted"
    )
    decision = resolve(incoming, release, IngressContext(harness.user_id, -99, rollout=True)).model_copy(
        update={"position": ExpectedPosition()}
    )
    async with pool.begin() as session:
        await TriggerRepository(session).record(incoming, decision)
    settings = await container.get(Settings)
    monkeypatch.setattr(settings, "admin_chat_id", harness.user_id + 1)
    await harness.message("/restricted", 140110)
    assert await active(harness, container) is None
    monkeypatch.setattr(settings, "admin_chat_id", harness.user_id)
    await harness.message("/flow_demo", 140111)
    before = await active(harness, container)
    await harness.message("/restricted", 140110)
    assert await active(harness, container) == before


async def test_trigger_rollback_validates_the_original_child_dependency_pins(ingress_flow):
    harness, container, _ = ingress_flow
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        for document in (child_document(), parent_document()):
            await flows.create(document)
            await flows.publish(document.id, 0, harness.user_id)
        triggers = await request.get(TriggerService)
        draft = await triggers.draft()
        binding = TriggerBinding.model_validate(
            {
                "id": "compose",
                "matcher": {"kind": "command", "key": "compose"},
                "target": {"kind": "scenario", "flow_id": "parent"},
            }
        )
        await triggers.save(draft.document.model_copy(update={"bindings": [*draft.document.bindings, binding]}), 0)
        original = await triggers.publish(1, harness.user_id)
        changed = child_document().model_dump(mode="json")
        changed["fields"]["answer"]["type"] = "integer"
        changed["outputs"]["answer"]["type"] = "integer"
        changed["nodes"][0]["input_type"] = "integer"
        await flows.save(FlowDocument.model_validate(changed), 0)
        await flows.publish("child", 1, harness.user_id)
        draft = await triggers.draft()
        await triggers.save(draft.document, 1)
        following = await triggers.publish(2, harness.user_id)
        await triggers.activate(original.id, following.id)
        assert (await triggers.current()).id == original.id
        assert (await flows.version("parent", 1)).dependencies == {"child": 1}
