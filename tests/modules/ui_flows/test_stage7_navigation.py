from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.methods import AnswerCallbackQuery, SendMessage
from sqlalchemy import func, select

from manashelper.core.config import get_settings
from manashelper.localization.locale import Locale
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.student_questions.callbacks import StudentQuestionsAnswerCallback, StudentQuestionsStep
from manashelper.modules.student_questions.orm import StudentQuestionsResponse
from manashelper.modules.student_questions.router import SESSION_KEY, StudentQuestionsForm
from manashelper.modules.ui_flows.application.rollout import RolloutService
from manashelper.modules.ui_flows.application.triggers import TriggerService
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiScreenDelivery
from manashelper.modules.ui_flows.infrastructure.trigger_orm import UiIngressReceipt
from manashelper.modules.ui_flows.presentation import features
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.ui_flows.triggers import trigger_document
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.presentation.callbacks import LocaleCallback
from manashelper.modules.users.ui_scenarios import user_scenarios
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from manashelper.platform.telegram.ui_scenarios import settings_document
from tests.modules.ui_flows.telegram_factory import TelegramHarness, container_for, dispatcher_for
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.ingress import LegacyTarget, ScenarioTarget
from ui_flows.domain.schema import FlowDocument
from ui_flows.domain.state import RuntimeUser

ADMIN = 991_450


@pytest_asyncio.fixture
async def stage7_flow(isolated_flow_pool, monkeypatch):
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(ADMIN))
    get_settings.cache_clear()
    try:
        async with Bot(token="123456:synthetic-stage7-ingress") as bot, container_for(isolated_flow_pool) as container:
            harness = TelegramHarness(bot, dispatcher_for(container, ADMIN, ingress=True), ADMIN)
            monkeypatch.setattr(bot.session, "make_request", harness.respond)
            await (await container.get(FlowTelegramCoordinator)).install_defaults(ADMIN)
            yield harness, container, isolated_flow_pool
    finally:
        get_settings.cache_clear()


async def active(container, user_id=ADMIN):
    async with catalog_request(container) as request:
        return await (await request.get(DialogService)).active(RuntimeUser(user_id, user_id))


async def delivery(pool, update_id):
    async with pool() as observer:
        screen = await observer.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == update_id))
        assert screen is not None and screen.status == "sent"
        return screen


def find_button(screen, identifier):
    return next(
        (index, button)
        for index, button in enumerate(button for row in screen.screen["buttons"] for button in row)
        if button["id"] == identifier
    )


async def click(harness, pool, screen_update_id, identifier, update_id):
    screen = await delivery(pool, screen_update_id)
    index, _ = find_button(screen, identifier)
    await harness.callback(f"uf:{screen.token}:{index}", screen.message_id, update_id)
    return screen, index


async def translated(container, key, *, locale="en", theme="basic"):
    async with catalog_request(container) as request:
        return (await (await request.get(TextCatalogService)).current()).gettext(key, locale, theme)


async def test_fresh_manifest_owns_preferences_settings_and_preserves_survey_compatibility(stage7_flow):
    _, container, _ = stage7_flow
    baseline = {binding.id: binding for binding in trigger_document().bindings}
    assert isinstance(baseline["cmd_language"].target, LegacyTarget)
    assert baseline["survey"].fallback_adapter == "student_questions"
    async with catalog_request(container) as request:
        current = await (await request.get(TriggerService)).current()
        bindings = {binding.id: binding for binding in current.manifest.document.bindings}
        for identifier, flow_id in (
            ("cmd_language", "select_locale"),
            ("set_open_language", "select_locale"),
            ("set_open_theme", "select_theme"),
            ("label_menu_settings", "settings"),
            ("set_back_to_settings", "settings"),
        ):
            assert isinstance(bindings[identifier].target, ScenarioTarget)
            assert bindings[identifier].target.flow_id == flow_id
        for identifier in ("cmd_language", "set_open_language", "set_open_theme"):
            assert bindings[identifier].policy == "call"
        assert bindings["survey"].target.flow_id == "student_questions"
        assert bindings["survey"].fallback_adapter == "student_questions"
        pins = {pin.flow_id for pin in current.manifest.scenarios}
        assert {"main_menu", "settings", "select_locale", "select_theme", "student_questions"} <= pins


async def test_settings_calls_preferences_and_returns_to_same_pinned_settings_then_root(stage7_flow):
    harness, container, pool = stage7_flow
    await harness.message("/start", 42100)
    root = await active(container)
    welcome = await delivery(pool, 42100)
    _, settings_button = find_button(welcome, "settings")
    await harness.message(settings_button["label"], 42101)
    settings = await active(container)
    assert settings.id == root.id and settings.flow_id == "settings" and settings.flow_version == 1
    assert settings.root_flow_id == "main_menu" and len(settings.frames) == 1
    assert settings.frames[0].flow_version == root.flow_version
    await click(harness, pool, 42101, "language", 42102)
    language = await active(container)
    assert language.id == root.id and language.flow_id == "select_locale" and len(language.frames) == 2
    old_language, old_index = await click(harness, pool, 42102, "ru", 42103)
    after_language = await active(container)
    assert after_language.id == settings.id and after_language.flow_id == "settings"
    assert after_language.flow_version == settings.flow_version and after_language.frames == settings.frames
    assert after_language.data == settings.data
    screen = await delivery(pool, 42103)
    assert screen.screen["locale"] == "ru" and screen.screen["theme"] == "basic"
    assert screen.screen["text"] == await translated(container, "settings.title", locale="ru")
    assert len(screen.screen["messages"]) == 1 and "Русский" in screen.screen["messages"][0]
    async with pool() as observer:
        saved = await observer.get(User, ADMIN)
        stamp = saved.updated_at
        event_count = await observer.scalar(select(func.count()).select_from(UiFlowEvent))
    sends = sum(isinstance(method, SendMessage) for method in harness.calls)
    await harness.callback(f"uf:{old_language.token}:{old_index}", old_language.message_id, 42103)
    assert await active(container) == after_language
    assert sum(isinstance(method, SendMessage) for method in harness.calls) == sends
    async with pool() as observer:
        assert (await observer.get(User, ADMIN)).updated_at == stamp
        assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == event_count
    await harness.callback(f"uf:{old_language.token}:{old_index}", old_language.message_id, 42104)
    assert isinstance(harness.calls[-1], AnswerCallbackQuery) and harness.calls[-1].show_alert
    assert await active(container) == after_language

    await click(harness, pool, 42103, "theme", 42105)
    assert (await active(container)).flow_id == "select_theme"
    await click(harness, pool, 42105, "halloween", 42106)
    after_theme = await active(container)
    assert after_theme.id == settings.id and after_theme.flow_id == "settings"
    assert after_theme.frames == settings.frames and after_theme.data == settings.data
    screen = await delivery(pool, 42106)
    assert (screen.screen["locale"], screen.screen["theme"]) == ("ru", "halloween")
    assert screen.screen["text"] == await translated(container, "settings.title", locale="ru", theme="halloween")
    assert len(screen.screen["messages"]) == 1
    await click(harness, pool, 42106, "back", 42107)
    returned = await active(container)
    assert returned.id == root.id and returned.flow_id == "main_menu" and returned.node_id == "main"
    assert returned.flow_version == root.flow_version and returned.frames == () and returned.data == root.data


async def test_global_language_interrupt_resumes_populated_demo_input_after_dispatcher_restart(stage7_flow):
    harness, container, pool = stage7_flow
    await harness.message("/flow_demo", 42200)
    _, form = find_button(await delivery(pool, 42200), "form")
    await harness.message(form["label"], 42201)
    await harness.message("retained form answer", 42202)
    await click(harness, pool, 42202, "back", 42203)
    before = await active(container)
    assert before.node_id == "answer" and before.data["answer"] == "retained form answer"
    old_input = await delivery(pool, 42203)
    await harness.message("/language", 42204)
    choice = await active(container)
    assert choice.id == before.id and choice.flow_id == "select_locale" and choice.flow_version == 1
    assert choice.frames[-1].resume_status == "waiting_input" and choice.frames[-1].data == before.data
    assert choice.frames[-1].flow_id == before.flow_id and choice.frames[-1].flow_version == before.flow_version
    async with container_for(pool) as restarted:
        harness.dispatcher = dispatcher_for(restarted, ADMIN, ingress=True)
        assert await active(restarted) == choice
        await click(harness, pool, 42204, "ky", 42205)
        restored = await active(restarted)
        assert restored.id == before.id and restored.flow_id == before.flow_id
        assert restored.node_id == before.node_id and restored.status == before.status
        assert restored.frames == before.frames and restored.data == before.data
        assert restored.flow_version == before.flow_version and restored.revision > choice.revision
        rendered = await delivery(pool, 42205)
        assert rendered.screen["locale"] == "ky"
        assert rendered.screen["text"] == await translated(restarted, "ui_flows.demo.prompt", locale="ky")
        sends = sum(isinstance(method, SendMessage) for method in harness.calls)
        await harness.message("/language", 42204)
        assert await active(restarted) == restored
        assert sum(isinstance(method, SendMessage) for method in harness.calls) == sends
        cancel_index, _ = find_button(old_input, "cancel")
        await harness.callback(f"uf:{old_input.token}:{cancel_index}", old_input.message_id, 42206)
        assert isinstance(harness.calls[-1], AnswerCallbackQuery) and harness.calls[-1].show_alert
        assert await active(restarted) == restored
        await harness.message("new form answer", 42207)
        confirmed = await active(restarted)
        assert confirmed.id == before.id and confirmed.node_id == "confirm"
        assert confirmed.data["answer"] == "new form answer" and confirmed.revision > restored.revision
    async with pool() as observer:
        assert (await observer.get(User, ADMIN)).locale == "ky"


async def test_global_language_uses_legacy_picker_without_clearing_obis_password_form(stage7_flow, monkeypatch):
    harness, container, pool = stage7_flow
    save = AsyncMock(side_effect=AssertionError("A navigation command must not be treated as an OBIS password"))
    monkeypatch.setattr(ObisService, "save_credentials", save)
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, ADMIN, ADMIN))
    await memory.set_state("ObisCredentialsForm:password")
    await memory.set_data({"student_number": "synthetic-student", "prompt_id": 441})
    original = await memory.get_data()
    await harness.message("/language", 42300)
    assert await memory.get_state() == "ObisCredentialsForm:password" and await memory.get_data() == original
    assert await active(container) is None
    picker = next(method for method in reversed(harness.calls) if isinstance(method, SendMessage))
    assert any(
        button.callback_data.startswith("locale:") for row in picker.reply_markup.inline_keyboard for button in row
    )
    await harness.callback(LocaleCallback(locale=Locale.RU).pack(), 500, 42301)
    assert await memory.get_state() == "ObisCredentialsForm:password" and await memory.get_data() == original
    assert await active(container) is None
    save.assert_not_awaited()
    async with pool() as observer:
        assert (await observer.get(User, ADMIN)).locale == "ru"
        receipt = await observer.get(UiIngressReceipt, (harness.bot.id, 42300))
        assert receipt.decision["kind"] == "legacy" and receipt.decision["adapter"] == "locale"
        assert await observer.scalar(select(func.count()).select_from(UiDialogSession)) == 0


async def test_survey_runtime_resumes_when_off_and_new_public_entry_uses_legacy_fallback(stage7_flow):
    harness, container, pool = stage7_flow
    await harness.message("/start student_questions", 42400)
    original = await active(container)
    assert original.flow_id == "student_questions"
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, ADMIN, ADMIN))
    assert await memory.get_state() is None
    async with catalog_request(container) as request:
        rollout = await request.get(RolloutService)
        state = await rollout.get()
        await rollout.set("off", state.revision, ADMIN)
    await harness.message("/start student_questions", 42401)
    resumed = await active(container)
    assert resumed == original
    await harness.message("/start student_questions", 42402, user_id=ADMIN + 1)
    assert await active(container, ADMIN + 1) is None
    other_memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, ADMIN + 1, ADMIN + 1))
    assert await other_memory.get_state() == StudentQuestionsForm.course.state
    async with pool() as observer:
        assert await observer.scalar(select(func.count()).select_from(UiDialogSession)) == 1
        denied_runtime = await observer.get(UiIngressReceipt, (harness.bot.id, 42402))
        assert denied_runtime.decision["kind"] == "legacy"
        assert denied_runtime.decision["adapter"] == "student_questions"
        receipt = await observer.get(UiIngressReceipt, (harness.bot.id, 42401))
        assert receipt.decision["kind"] == "launch" and receipt.decision["flow_id"] == "student_questions"


async def test_active_legacy_survey_keeps_ownership_and_finishes_when_runtime_rollout_is_off(stage7_flow):
    harness, container, pool = stage7_flow
    # Represent a form already open before the scenario cutover; its MemoryStorage answers remain authoritative.
    await harness.message("/hide_keyboard", 42500)
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, ADMIN, ADMIN))
    await memory.set_state(StudentQuestionsForm.search)
    await memory.set_data({SESSION_KEY: "legacy-before-cutover", "overwrite": False, "course": "3"})
    async with catalog_request(container) as request:
        rollout = await request.get(RolloutService)
        state = await rollout.get()
        await rollout.set("off", state.revision, ADMIN)
    await harness.callback(
        StudentQuestionsAnswerCallback(
            session_id="legacy-before-cutover", step=StudentQuestionsStep.SEARCH, answer="no"
        ).pack(),
        700,
        42501,
    )
    assert await memory.get_state() == StudentQuestionsForm.beta.state
    assert (await memory.get_data())["course"] == "3"
    assert (await memory.get_data())["had_questions"] is False
    assert await active(container) is None
    await harness.callback(
        StudentQuestionsAnswerCallback(
            session_id="legacy-before-cutover", step=StudentQuestionsStep.BETA, answer="yes"
        ).pack(),
        700,
        42502,
    )
    assert await memory.get_state() is None
    assert await active(container) is None
    async with pool() as observer:
        saved = await observer.get(StudentQuestionsResponse, ADMIN)
        assert saved.course == "3" and saved.had_questions is False and saved.wants_beta is True
        assert await observer.scalar(select(func.count()).select_from(UiDialogSession)) == 0
        for update_id in (42501, 42502):
            receipt = await observer.get(UiIngressReceipt, (harness.bot.id, update_id))
            assert receipt.decision["kind"] == "legacy" and receipt.decision["adapter"] == "student_questions"


async def test_legacy_survey_deep_link_stays_legacy_with_runtime_enabled(stage7_flow):
    harness, container, pool = stage7_flow
    await harness.message("/hide_keyboard", 42600)
    memory = FSMContext(harness.dispatcher.storage, StorageKey(harness.bot.id, ADMIN, ADMIN))
    await memory.set_state(StudentQuestionsForm.course)
    await memory.set_data({SESSION_KEY: "pre-cutover-survey", "overwrite": False})
    await harness.message("/start student_questions", 42601)
    assert await memory.get_state() == StudentQuestionsForm.course.state
    assert await active(container) is None
    # Existing legacy deep-link behavior may restart its own form; it must never create a runtime owner as well.
    legacy_id = (await memory.get_data())[SESSION_KEY]
    await harness.callback(
        StudentQuestionsAnswerCallback(session_id=legacy_id, step=StudentQuestionsStep.COURSE, answer="4").pack(),
        701,
        42602,
    )
    assert await memory.get_state() == StudentQuestionsForm.search.state
    assert (await memory.get_data())["course"] == "4"
    async with pool() as observer:
        assert await observer.scalar(select(func.count()).select_from(UiDialogSession)) == 0
        receipt = await observer.get(UiIngressReceipt, (harness.bot.id, 42601))
        assert receipt.decision["kind"] == "legacy" and receipt.decision["adapter"] == "student_questions"


@pytest.mark.parametrize("unpublished", ["select_locale", "settings"])
async def test_authored_unpublished_dependency_keeps_startup_compatible_and_seed_retries_without_changing_release(
    isolated_flow_pool, unpublished
):
    documents = {document.id: document for document in [*user_scenarios(), settings_document()]}
    authored = documents[unpublished].model_copy(deep=True)
    authored.layout.clear()
    async with container_for(isolated_flow_pool) as container:
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            await flows.create(authored)
        coordinator = await container.get(FlowTelegramCoordinator)
        await coordinator.install_defaults(ADMIN)
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            draft = await flows.get(unpublished)
            assert draft.document == authored and draft.revision == 0 and draft.published_version is None
            triggers = await request.get(TriggerService)
            compatibility = await triggers.current()
            assert compatibility.id == 1 and compatibility.manifest.scenarios == []
            assert all(binding.target.kind == "legacy" for binding in compatibility.manifest.document.bindings)
            assert (await triggers.draft()).document != compatibility.manifest.document
            # Existing unpublished Settings can be published after its already seeded user dependencies.
            await flows.publish(unpublished, 0, ADMIN)
        await coordinator.install_defaults(ADMIN)
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            assert (await flows.get(unpublished)).document == authored
            assert (await flows.get(unpublished)).revision == 0
            for identifier in ("select_locale", "select_theme", "settings", "main_menu", "student_questions"):
                assert (await flows.get(identifier)).published_version == 1
            unchanged = await (await request.get(TriggerService)).current()
            assert unchanged.id == compatibility.id and unchanged.manifest == compatibility.manifest


async def test_call_confirmation_precedes_public_feature_entry_and_replay_never_repeats_handoff(
    stage7_flow, monkeypatch
):
    harness, container, pool = stage7_flow
    document = FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "preference_then_handoff",
            "entry": "preference",
            "nodes": [
                {
                    "kind": "call",
                    "id": "preference",
                    "flow": "select_locale",
                    "outcomes": {"completed": "notifications", "cancelled": "notifications"},
                },
                {"kind": "end", "id": "notifications", "status": "handed_off", "feature": "notifications"},
            ],
        }
    )
    async with catalog_request(container) as request:
        flows = await request.get(FlowService)
        await flows.create(document)
        await flows.publish(document.id, 0, ADMIN)
    original = features.show_notifications
    entries = []

    async def observe_public_entry(message, user_id, settings):
        entries.append((message, user_id))
        await original(message, user_id, settings)

    monkeypatch.setattr(features, "show_notifications", observe_public_entry)
    await harness.message("/flow_demo " + document.id, 42700)
    source = await active(container)
    assert source.flow_id == "select_locale" and source.root_flow_id == document.id
    start_calls = len(harness.calls)
    picker, index = await click(harness, pool, 42700, "ru", 42701)
    assert await active(container) is None
    sent = [method for method in harness.calls[start_calls:] if isinstance(method, SendMessage)]
    assert len(sent) == 2 and "Русский" in sent[0].text
    assert sent[1].text == await translated(container, "notifications.title", locale="ru")
    assert len(entries) == 1 and entries[0][1] == ADMIN
    assert entries[0][0].message_id == picker.message_id and entries[0][0].chat.id == ADMIN
    async with pool() as observer:
        handoff = await observer.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 42701))
        assert handoff.status == "sent" and len(handoff.message_ids) == 1
        state = await observer.get(UiDialogSession, source.id)
        assert state.status == "handed_off" and state.node_id == "notifications"
    calls = len(harness.calls)
    await harness.callback(f"uf:{picker.token}:{index}", picker.message_id, 42701)
    assert len(entries) == 1
    assert all(isinstance(method, AnswerCallbackQuery) for method in harness.calls[calls:])
