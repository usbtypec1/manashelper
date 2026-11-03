import pytest
from aiogram import Bot
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import func, select

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.ui_flows.infrastructure.orm import UiDialogSession, UiFlowEvent, UiScreenDelivery
from manashelper.modules.ui_flows.presentation.coordinator import FlowTelegramCoordinator
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.ui_delegates import UserUiDelegates
from manashelper.modules.users.ui_scenarios import user_scenarios
from manashelper.platform.i18n.request import catalog_request
from manashelper.platform.i18n.service import TextCatalogService
from tests.modules.ui_flows.telegram_factory import TelegramHarness, container_for
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ButtonEvent
from ui_flows.domain.schema import FlowDocument

USER_ID = 991_797
LANGUAGE_NAMES = {"en": "English", "ru": "Русский", "ky": "Кыргызча", "tr": "Türkçe", "zh": "中文"}


async def seed(pool, *, locale="en", theme="basic"):
    async with pool.begin() as session:
        session.add(User(id=USER_ID, full_name="Durable preference test", locale=locale, theme=theme))
    async with container_for(pool) as container, catalog_request(container) as request:
        flows = await request.get(FlowService)
        for document in user_scenarios():
            await flows.create(document)
            await flows.publish(document.id, 0, USER_ID)


def choice(state, update_id, selected):
    return ButtonEvent(
        kind="button",
        update_id=update_id,
        user_id=USER_ID,
        chat_id=USER_ID,
        session_id=str(state.id),
        expected_revision=state.revision,
        button_id=selected,
    )


async def start(container, flow_id, update_id):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        return await (await request.get(DialogService)).start(flow_id, user, update_id)


async def select_choice(container, state, update_id, selected):
    async with catalog_request(container) as request:
        user = await FlowTelegramCoordinator._user(request, USER_ID)
        result = await (await request.get(DialogService)).handle(choice(state, update_id, selected), user)
        pending = await FlowTelegramCoordinator._prepare(request, result, user, update_id)
        return result, pending


async def selected_notice(request, flow_id, selected, locale, theme):
    flows = await request.get(FlowService)
    draft = await flows.get(flow_id)
    version = await flows.version(flow_id, draft.published_version)
    snapshot = await (await request.get(TextCatalogService)).version(version.text_catalog_release or 1)
    if flow_id == "select_locale":
        return snapshot.gettext("language.selected", locale, theme).format(language=LANGUAGE_NAMES[selected])
    name = snapshot.gettext("theme." + selected, locale, theme)
    return snapshot.gettext("theme.selected", locale, theme).format(theme=name)


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("theme", list(Theme))
async def test_standalone_preferences_commit_and_render_all_locales_and_themes(isolated_flow_pool, locale, theme):
    initial_locale = "ru" if locale == Locale.EN else "en"
    initial_theme = "halloween" if theme == Theme.BASIC else "basic"
    await seed(isolated_flow_pool, locale=initial_locale, theme=initial_theme)
    async with container_for(isolated_flow_pool) as container:
        language = await start(container, "select_locale", 40100)
        result, screen = await select_choice(container, language.state, 40101, locale.value)
        assert result.state.status == "completed" and result.state.node_id == "completed"
        assert screen.screen.locale == locale.value and screen.screen.theme == initial_theme
        async with catalog_request(container) as request:
            assert screen.screen.text == await selected_notice(
                request, "select_locale", locale.value, locale.value, initial_theme
            )
        appearance = await start(container, "select_theme", 40102)
        result, screen = await select_choice(container, appearance.state, 40103, theme.value)
        assert result.state.status == "completed" and result.state.node_id == "completed"
        assert screen.screen.locale == locale.value and screen.screen.theme == theme.value
        async with catalog_request(container) as request:
            assert screen.screen.text == await selected_notice(
                request, "select_theme", theme.value, locale.value, theme.value
            )
    async with isolated_flow_pool() as observer:
        saved = await observer.get(User, USER_ID)
        assert (saved.locale, saved.theme) == (locale.value, theme.value)
        assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 4


@pytest.mark.parametrize("flow_id", ["select_locale", "select_theme"])
async def test_cancel_preserves_existing_preferences(isolated_flow_pool, flow_id):
    await seed(isolated_flow_pool, locale="tr", theme="halloween")
    async with container_for(isolated_flow_pool) as container:
        waiting = await start(container, flow_id, 40200)
        result, screen = await select_choice(container, waiting.state, 40201, "cancel")
        assert result.state.node_id == "cancelled" and result.state.status == "completed"
        assert (screen.screen.locale, screen.screen.theme) == ("tr", "halloween")
        async with catalog_request(container) as request:
            snapshot = await (await request.get(TextCatalogService)).version(screen.screen.text_catalog_release)
            assert screen.screen.text == snapshot.gettext("common.cancelled", "tr", "halloween")
    async with isolated_flow_pool() as observer:
        saved = await observer.get(User, USER_ID)
        assert (saved.locale, saved.theme) == ("tr", "halloween")


@pytest.mark.parametrize(
    "flow_id,method,selected", [("select_locale", "set_locale", "ru"), ("select_theme", "set_theme", "halloween")]
)
async def test_caught_failure_rolls_back_preference_position_and_receipt_together(
    isolated_flow_pool, monkeypatch, flow_id, method, selected
):
    await seed(isolated_flow_pool)
    original = getattr(UserUiDelegates, method)

    async def fail_after_save(self, context, arguments):
        await original(self, context, arguments)
        raise RuntimeError("failure after saved preference")

    async with container_for(isolated_flow_pool) as container:
        waiting = await start(container, flow_id, 40300)
        with monkeypatch.context() as patch:
            patch.setattr(UserUiDelegates, method, fail_after_save)
            # Catch inside a REQUEST which then commits: the dialog's savepoint must undo the setting too.
            async with catalog_request(container) as request:
                dialogs = await request.get(DialogService)
                user = await FlowTelegramCoordinator._user(request, USER_ID)
                with pytest.raises(RuntimeError, match="failure after saved preference"):
                    await dialogs.handle(choice(waiting.state, 40301, selected), user)
                assert await dialogs.get(waiting.state.id, user) == waiting.state
        async with isolated_flow_pool() as observer:
            saved = await observer.get(User, USER_ID)
            assert (saved.locale, saved.theme) == ("en", "basic")
            assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 1
        result, _ = await select_choice(container, waiting.state, 40301, selected)
        assert result.state.status == "completed" and result.state.revision == waiting.state.revision + 1


@pytest.mark.parametrize("flow_id,selected", [("select_locale", "ky"), ("select_theme", "halloween")])
async def test_restart_accepts_saved_callback_and_event_replay_does_not_write_again(
    isolated_flow_pool, monkeypatch, flow_id, selected
):
    await seed(isolated_flow_pool)
    async with Bot(token="123456:synthetic-preference-callback") as bot:
        transport = TelegramHarness(bot, None, USER_ID)
        monkeypatch.setattr(bot.session, "make_request", transport.respond)
        async with container_for(isolated_flow_pool) as first:
            waiting = await start(first, flow_id, 40400)
            async with catalog_request(first) as request:
                user = await FlowTelegramCoordinator._user(request, USER_ID)
                pending = await FlowTelegramCoordinator._prepare(request, waiting, user, 40400)
            await (await first.get(FlowTelegramCoordinator))._deliver(bot, pending)
        actions = next(
            method
            for method in reversed(transport.calls)
            if isinstance(method, SendMessage) and isinstance(method.reply_markup, InlineKeyboardMarkup)
        )
        index = next(
            index
            for index, button in enumerate(b for row in pending.screen.buttons for b in row)
            if button.id == selected
        )
        assert actions.reply_markup.inline_keyboard[index][0].callback_data == f"uf:{pending.token}:{index}"
        async with isolated_flow_pool() as observer:
            persisted = await observer.get(UiScreenDelivery, pending.token)
            message_id = persisted.message_id
            assert persisted.status == "sent"
        async with container_for(isolated_flow_pool) as restarted:
            async with catalog_request(restarted) as request:
                dialogs = await request.get(DialogService)
                user = await FlowTelegramCoordinator._user(request, USER_ID)
                assert await dialogs.get(waiting.state.id, user) == waiting.state
            coordinator = await restarted.get(FlowTelegramCoordinator)
            await coordinator.callback(bot, USER_ID, 40401, pending.token, index, message_id, "saved-preference")
            async with isolated_flow_pool() as observer:
                finished = await observer.get(UiDialogSession, waiting.state.id)
                saved = await observer.get(User, USER_ID)
                stamp = saved.updated_at
                assert finished.status == "completed" and finished.revision == 1
                assert (saved.locale, saved.theme) == (
                    ("ky", "basic") if flow_id == "select_locale" else ("en", "halloween")
                )
                assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 2
            # DialogService processes the same admitted event as a duplicate, despite its old expected_revision.
            duplicate, same_screen = await select_choice(restarted, waiting.state, 40401, selected)
            assert duplicate.outcome == "duplicate" and duplicate.state.revision == 1
            async with isolated_flow_pool() as observer:
                saved = await observer.get(User, USER_ID)
                assert saved.updated_at == stamp
                assert await observer.scalar(select(func.count()).select_from(UiFlowEvent)) == 2
                assert (
                    same_screen.token
                    == (
                        await observer.scalar(select(UiScreenDelivery).where(UiScreenDelivery.update_id == 40401))
                    ).token
                )


def parent_document(child):
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": "preference_parent",
            "entry": "preference",
            "fields": {"marker": {"type": "text"}, "selected": {"type": "text"}, "selected_name": {"type": "text"}},
            "initial_data": {
                "marker": "keep-parent-answer",
                "selected": "parent-choice",
                "selected_name": "parent-name",
            },
            "nodes": [
                {
                    "kind": "call",
                    "id": "preference",
                    "flow": child,
                    "outcomes": {"completed": "prompt", "cancelled": "prompt"},
                },
                {
                    "kind": "menu",
                    "id": "prompt",
                    "keyboard": "reply",
                    "text": [{"kind": "catalog", "key": "menu.settings"}],
                    "buttons": [],
                },
            ],
        }
    )


@pytest.mark.parametrize(
    "flow_id,selected,locale,theme",
    [
        ("select_locale", "ru", "ru", "halloween"),
        ("select_locale", "zh", "zh", "basic"),
        ("select_theme", "basic", "ky", "basic"),
        ("select_theme", "halloween", "tr", "halloween"),
    ],
)
async def test_called_preference_restores_parent_locals_and_delivers_notice_in_new_preferences(
    isolated_flow_pool, flow_id, selected, locale, theme
):
    await seed(isolated_flow_pool, locale="en" if flow_id == "select_locale" else locale, theme=theme)
    async with container_for(isolated_flow_pool) as container:
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            parent = parent_document(flow_id)
            await flows.create(parent)
            await flows.publish(parent.id, 0, USER_ID)
        waiting = await start(container, parent.id, 40500)
        assert waiting.state.flow_id == flow_id and len(waiting.state.frames) == 1
        result, screen = await select_choice(container, waiting.state, 40501, selected)
        assert result.state.id == waiting.state.id and result.state.flow_id == parent.id
        assert result.state.node_id == "prompt" and result.state.status == "waiting_button"
        assert result.state.frames == () and result.state.data == parent.initial_data
        async with catalog_request(container) as request:
            assert screen.screen.messages == [await selected_notice(request, flow_id, selected, locale, theme)]
            snapshot = await (await request.get(TextCatalogService)).version(screen.screen.text_catalog_release)
            assert screen.screen.text == snapshot.gettext("menu.settings", locale, theme)
        assert (screen.screen.locale, screen.screen.theme) == (locale, theme)
    async with isolated_flow_pool() as observer:
        saved = await observer.get(UiDialogSession, waiting.state.id)
        assert saved.data == parent.initial_data and saved.frames == []


@pytest.mark.parametrize("flow_id,selected", [("select_locale", "ru"), ("select_theme", "halloween")])
async def test_call_return_notice_uses_child_text_pin_and_parent_prompt_uses_parent_pin(
    isolated_flow_pool, flow_id, selected
):
    await seed(isolated_flow_pool, locale="ru")
    async with container_for(isolated_flow_pool) as container:
        async with catalog_request(container) as request:
            texts = await request.get(TextCatalogService)
            draft = await texts.draft()
            for key, content in (
                ("language.selected", "Current language {language}"),
                ("theme.selected", "Current theme {theme}"),
                ("menu.settings", "Current parent prompt"),
            ):
                entry = next(item for item in draft.document.entries if item.key == key)
                entry = entry.model_copy(
                    update={
                        "variants": tuple(variant.model_copy(update={"text": content}) for variant in entry.variants)
                    }
                )
                draft = await texts.save_entry(key, entry, draft.revision)
            publication = await texts.publish(draft.revision, USER_ID)
            assert publication.id == 2
        async with catalog_request(container) as request:
            flows = await request.get(FlowService)
            parent = parent_document(flow_id)
            await flows.create(parent)
            published = await flows.publish(parent.id, 0, USER_ID)
            assert published.text_catalog_release == 2
            assert (await flows.version(flow_id, 1)).text_catalog_release == 1
        waiting = await start(container, parent.id, 40600)
        result, screen = await select_choice(container, waiting.state, 40601, selected)
        theme = "basic" if flow_id == "select_locale" else "halloween"
        async with catalog_request(container) as request:
            expected = await selected_notice(request, flow_id, selected, "ru", theme)
            assert not expected.startswith("Current ")
            assert screen.screen.messages == [expected]
        assert screen.screen.text == "Current parent prompt" and screen.screen.text_catalog_release == 2
        assert result.state.data == parent.initial_data
