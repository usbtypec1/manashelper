import asyncio
from dataclasses import replace

import pytest
from dishka import Provider, Scope, provide
from sqlalchemy import func, select

from manashelper.modules.ui_flows.application.effect_worker import EffectWorker
from manashelper.modules.ui_flows.infrastructure.effect_orm import UiExternalOperation
from manashelper.modules.ui_flows.infrastructure.effects import EffectRepository
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiUserTransition
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.ui_scenarios import user_scenarios
from manashelper.platform.i18n.request import catalog_request
from tests.modules.ui_flows.telegram_factory import container_for
from ui_flows.application.delegates import DelegateBinding, ExternalDelegateRegistry
from ui_flows.application.delivery import ScreenDeliveryService
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ButtonEvent, DelegateDefinition, DelegateResult, InputEvent
from ui_flows.domain.ingress import ExpectedPosition
from ui_flows.domain.schema import FlowDocument
from ui_flows.errors import StaleEventError

USER_ID = 991_798


def text(value):
    return {"kind": "inline", "translations": {"en": value}}


def button(identifier, target):
    return {"kind": "transition", "id": identifier, "label": text(identifier.title()), "target": target}


def nested_documents():
    leaf = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "interrupt_leaf",
            "entry": "answer",
            "fields": {"answer": {"type": "text"}, "marker": {"type": "text"}},
            "initial_data": {"answer": "retained answer", "marker": "retained child local"},
            "outputs": {"answer": {"type": "text"}},
            "outcomes": ["completed", "cancelled"],
            "nodes": [
                {
                    "kind": "input",
                    "id": "answer",
                    "text": [text("Answer before interrupt")],
                    "field": "answer",
                    "input_type": "text",
                    "next": "done",
                    "error": text("Enter text"),
                    "buttons": [[button("cancel", "cancelled")]],
                },
                {
                    "kind": "return",
                    "id": "done",
                    "outcome": "completed",
                    "values": {"answer": {"kind": "ref", "scope": "data", "field": "answer"}},
                },
                {
                    "kind": "return",
                    "id": "cancelled",
                    "outcome": "cancelled",
                    "values": {"answer": {"kind": "ref", "scope": "data", "field": "answer"}},
                },
            ],
        }
    )
    parent = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "interrupt_root",
            "entry": "child",
            "fields": {"answer": {"type": "text", "nullable": True}, "marker": {"type": "text"}},
            "initial_data": {"answer": None, "marker": "retained parent local"},
            "nodes": [
                {
                    "kind": "call",
                    "id": "child",
                    "flow": leaf.id,
                    "results": {"answer": "answer"},
                    "outcomes": {"completed": "ready", "cancelled": "ready"},
                },
                {"kind": "menu", "id": "ready", "keyboard": "reply", "text": [text("Parent")], "buttons": []},
            ],
        }
    )
    return leaf, parent


async def seed(pool, *documents, overrides=()):
    async with pool.begin() as session:
        session.add(User(id=USER_ID, full_name="Durable interrupt test", locale="en", theme="basic"))
    async with container_for(pool, *overrides) as container, catalog_request(container) as request:
        flows = await request.get(FlowService)
        for document in [*user_scenarios(), *documents]:
            await flows.create(document)
            await flows.publish(document.id, 0, USER_ID)


async def start(container, flow_id, update_id):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).start(flow_id, user, update_id)


async def interrupt(container, flow_id, update_id, source=None):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).interrupt(
            flow_id,
            user,
            update_id,
            position=ExpectedPosition(session_id=str(source.id), revision=source.revision) if source else None,
        )


async def choose(container, state, update_id, identifier):
    event = ButtonEvent(
        kind="button",
        update_id=update_id,
        user_id=USER_ID,
        chat_id=USER_ID,
        session_id=str(state.id),
        expected_revision=state.revision,
        button_id=identifier,
    )
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).handle(event, user)


async def current(container, session_id):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).get(session_id, user)


@pytest.mark.parametrize("preference,selection", [("select_locale", "ru"), ("select_theme", "halloween")])
async def test_restart_restores_nested_input_with_original_pins_locals_and_fresh_revision(
    isolated_flow_pool, preference, selection
):
    leaf, root = nested_documents()
    await seed(isolated_flow_pool, leaf, root)
    async with container_for(isolated_flow_pool) as first:
        original = await start(first, root.id, 41100)
        assert original.state.flow_id == leaf.id and original.state.flow_version == 1
        assert len(original.state.frames) == 1 and original.state.root_flow_id == root.id
        async with catalog_request(first) as request:
            user = await FlowTelegramCoordinator._user(request, USER_ID)
            delivery = await FlowTelegramCoordinator._prepare(request, original, user, 41100)
            await (await request.get(ScreenDeliveryService)).acknowledge(delivery.token, 117)
        opened = await interrupt(first, preference, 41101, original.state)
        assert opened.state.id == original.state.id and opened.state.flow_version == 1
        assert opened.state.revision == original.state.revision + 1
        frame = opened.state.frames[-1]
        assert (frame.flow_id, frame.flow_version, frame.node_id, frame.resume_status) == (
            leaf.id,
            1,
            "answer",
            "waiting_input",
        )
        assert frame.revision == original.state.revision and frame.data == original.state.data
        async with catalog_request(first) as request:
            # Subsequent child/root/preference publications cannot mutate any suspended pin.
            flows = await request.get(FlowService)
            for identifier in (leaf.id, root.id, preference):
                draft = await flows.get(identifier)
                await flows.save(draft.document, draft.revision)
                await flows.publish(identifier, draft.revision + 1, USER_ID)
        async with isolated_flow_pool() as observer:
            saved = await observer.get(UiDialogSession, original.state.id)
            assert saved.frames[-1]["resume_status"] == "waiting_input"
            assert saved.frames[-1]["revision"] == original.state.revision
            assert saved.frames[0]["flow_version"] == 1

    async with container_for(isolated_flow_pool) as restarted:
        assert await current(restarted, original.state.id) == opened.state
        repeated = await interrupt(restarted, preference, 41101, original.state)
        assert repeated.outcome == "duplicate" and repeated.state == opened.state
        with pytest.raises(StaleEventError):
            await interrupt(restarted, preference, 41102, original.state)
        restored = await choose(restarted, opened.state, 41103, selection)
        assert restored.state.id == original.state.id and restored.state.flow_id == leaf.id
        assert restored.state.flow_version == 1 and restored.state.node_id == "answer"
        assert restored.state.status == "waiting_input" and restored.state.revision > opened.state.revision
        assert restored.state.frames == original.state.frames and restored.state.data == original.state.data
        assert restored.state.effect_revision is None
        replay = await choose(restarted, opened.state, 41103, selection)
        assert replay.outcome == "duplicate" and replay.state == restored.state
        async with catalog_request(restarted) as request:
            user = await FlowTelegramCoordinator._user(request, USER_ID)
            with pytest.raises(StaleEventError):
                await (await request.get(ScreenDeliveryService)).callback(delivery.token, 0, 117, user)
            event = InputEvent(
                kind="input",
                update_id=41104,
                user_id=USER_ID,
                chat_id=USER_ID,
                session_id=str(restored.state.id),
                expected_revision=restored.state.revision,
                text="final answer",
            )
            completed = await (await request.get(DialogService)).handle(event, user)
            assert completed.state.id == original.state.id and completed.state.flow_id == root.id
            assert completed.state.flow_version == 1 and completed.state.frames == ()
            assert completed.state.data == {"answer": "final answer", "marker": "retained parent local"}
        async with isolated_flow_pool() as observer:
            assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 4
            assert await observer.scalar(select(func.count()).select_from(UiDialogSession)) == 1


async def test_nested_preference_cancellation_returns_to_each_wait_after_restart(isolated_flow_pool):
    leaf, root = nested_documents()
    await seed(isolated_flow_pool, leaf, root)
    async with container_for(isolated_flow_pool) as first:
        original = await start(first, root.id, 41200)
        language = await interrupt(first, "select_locale", 41201, original.state)
        appearance = await interrupt(first, "select_theme", 41202, language.state)
        assert len(appearance.state.frames) == 3
        assert appearance.state.frames[-1].resume_status == "waiting_button"
    async with container_for(isolated_flow_pool) as restarted:
        assert await current(restarted, original.state.id) == appearance.state
        back_to_language = await choose(restarted, appearance.state, 41203, "cancel")
        assert back_to_language.state.flow_id == "select_locale" and back_to_language.state.node_id == "choose"
        assert back_to_language.state.frames == language.state.frames
        back_to_input = await choose(restarted, back_to_language.state, 41204, "cancel")
        assert back_to_input.state.flow_id == leaf.id and back_to_input.state.status == "waiting_input"
        assert back_to_input.state.frames == original.state.frames and back_to_input.state.data == original.state.data
        assert [
            result.state.revision for result in (original, language, appearance, back_to_language, back_to_input)
        ] == list(range(5))
    async with isolated_flow_pool() as observer:
        saved = await observer.get(User, USER_ID)
        assert (saved.locale, saved.theme) == ("en", "basic")


def external_override(handler):
    definition = DelegateDefinition.model_validate(
        {
            "id": "test.interrupt_external",
            "effect": "external",
            "outputs": {"reply": {"type": "text"}},
            "outcomes": ["success"],
        }
    )
    registry = ExternalDelegateRegistry([DelegateBinding(definition, handler)])

    class External(Provider):
        @provide(scope=Scope.APP, override=True)
        def external_registry(self) -> ExternalDelegateRegistry:
            return registry

    return External()


def external_document():
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "interrupt_effect",
            "entry": "fetch",
            "fields": {"reply": {"type": "text", "nullable": True}, "marker": {"type": "text"}},
            "initial_data": {"reply": None, "marker": "retained effect input"},
            "nodes": [
                {
                    "kind": "action",
                    "id": "fetch",
                    "delegate": "test.interrupt_external",
                    "results": {"reply": "reply"},
                    "outcomes": {"success": "ready"},
                    "waiting_text": [text("Please wait")],
                },
                {"kind": "menu", "id": "ready", "text": [text("Ready")], "keyboard": "reply", "buttons": []},
            ],
        }
    )


async def operation(container):
    async with catalog_request(container) as request:
        operations = await (await request.get(EffectRepository)).pending()
        assert len(operations) == 1
        return await (await request.get(EffectRepository)).get(operations[0])


async def apply(container, operation_id):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).apply_effect(operation_id, user)


@pytest.mark.parametrize("succeeded_before_interrupt", [False, True])
async def test_effect_executes_once_while_suspended_and_applies_only_after_nested_returns(
    isolated_flow_pool, succeeded_before_interrupt
):
    calls = []

    async def execute(context, arguments):
        calls.append(context.event_id)
        return DelegateResult("success", {"reply": "persisted external result"})

    override = external_override(execute)
    document = external_document()
    await seed(isolated_flow_pool, document, overrides=(override,))
    async with container_for(isolated_flow_pool, override) as first:
        waiting = await start(first, document.id, 41300)
        prepared = await operation(first)
        assert prepared.matches_position(waiting.state)
        if succeeded_before_interrupt:
            assert (await (await first.get(EffectWorker)).run(prepared.id)).status == "succeeded"
        language = await interrupt(first, "select_locale", 41301, waiting.state)
        appearance = await interrupt(first, "select_theme", 41302, language.state)
        assert prepared.matches_position(appearance.state, suspended=True)
        assert not prepared.matches_position(appearance.state)
        assert not prepared.matches_position(replace(appearance.state, user_id=USER_ID + 1), suspended=True)
        worker = await first.get(EffectWorker)
        assert (await worker.run(prepared.id)).status == "succeeded"
        assert await apply(first, prepared.id) is None
        assert await current(first, waiting.state.id) == appearance.state
        async with isolated_flow_pool() as observer:
            assert (await observer.get(UiExternalOperation, prepared.id)).status == "succeeded"

    async with container_for(isolated_flow_pool, override) as restarted:
        worker = await restarted.get(EffectWorker)
        assert (await worker.run(prepared.id)).status == "succeeded" and calls == [str(prepared.id)]
        language_again = await choose(restarted, appearance.state, 41303, "cancel")
        assert await apply(restarted, prepared.id) is None
        restored = await choose(restarted, language_again.state, 41304, "ru")
        assert restored.state.id == waiting.state.id and restored.state.flow_id == document.id
        assert restored.state.status == "waiting_effect" and restored.state.node_id == "fetch"
        assert restored.state.revision == 4 and restored.state.effect_revision == prepared.revision == 0
        assert restored.state.data == waiting.state.data and restored.state.frames == ()
        assert prepared.matches_position(restored.state)
        async with isolated_flow_pool() as observer:
            saved = await observer.get(UiDialogSession, waiting.state.id)
            assert saved.effect_revision == 0
            assert await observer.scalar(select(func.count()).select_from(UiExternalOperation)) == 1
        finished = await apply(restarted, prepared.id)
        assert finished.state.node_id == "ready" and finished.state.revision == 5
        assert finished.state.effect_revision is None and finished.state.data["reply"] == "persisted external result"
        assert finished.state.data["marker"] == "retained effect input"
        assert await apply(restarted, prepared.id) is None and await worker.run(prepared.id) is None
        assert calls == [str(prepared.id)]
    async with isolated_flow_pool() as observer:
        assert (await observer.get(UiExternalOperation, prepared.id)).status == "applied"
        assert (await observer.get(UiDialogSession, waiting.state.id)).effect_revision is None
        assert (
            await observer.scalar(
                select(func.count()).select_from(UiUserTransition).where(UiUserTransition.operation_id == prepared.id)
            )
            == 1
        )


async def test_unknown_effect_is_not_reclaimed_after_interrupt_return_and_restart(isolated_flow_pool):
    entered = asyncio.Event()
    calls = []

    async def execute(context, arguments):
        calls.append(context.event_id)
        entered.set()
        await asyncio.Event().wait()

    override = external_override(execute)
    document = external_document()
    await seed(isolated_flow_pool, document, overrides=(override,))
    async with container_for(isolated_flow_pool, override) as first:
        waiting = await start(first, document.id, 41400)
        prepared = await operation(first)
        language = await interrupt(first, "select_locale", 41401, waiting.state)
        task = asyncio.create_task((await first.get(EffectWorker)).run(prepared.id))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        restored = await choose(first, language.state, 41402, "cancel")
        assert restored.state.status == "waiting_effect" and restored.state.effect_revision == 0
    async with container_for(isolated_flow_pool, override) as restarted:
        assert await (await restarted.get(EffectWorker)).run(prepared.id) is None
        assert await apply(restarted, prepared.id) is None
        assert await current(restarted, waiting.state.id) == restored.state
        async with catalog_request(restarted) as request:
            repository = await request.get(EffectRepository)
            assert prepared.id not in await repository.pending()
            saved = await repository.get(prepared.id)
            assert saved.status == "unknown" and saved.result is None
        assert calls == [str(prepared.id)]
