import asyncio
from runpy import run_path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, User
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dishka.integrations.aiogram import CONTAINER_NAME
from pydantic import ValidationError
from sqlalchemy import text

from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.users.application.locale import LocaleService
from manashelper.modules.users.application.theme import ThemeService
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.presentation.callbacks import ThemeCallback
from manashelper.modules.users.presentation.routers import theme
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
from manashelper.platform.telegram.filters.translated_text import TranslatedText
from manashelper.platform.telegram.keyboards.settings import build_settings_keyboard
from manashelper.platform.telegram.middlewares.i18n import LocaleMiddleware
from manashelper.platform.telegram.navigation import build_main_keyboard
from tests.paths import PROJECT_ROOT


@pytest.fixture
def context(monkeypatch):
    bot = Bot(token="123456:development-placeholder")
    user = User(id=976001, is_bot=False, first_name="Student")
    message = Message(message_id=1, date=0, chat=Chat(id=user.id, type="private"), from_user=user).as_(bot)
    callback = CallbackQuery(id="theme", from_user=user, message=message, chat_instance="chat").as_(bot)
    request = AsyncMock(return_value=message)
    monkeypatch.setattr(bot.session, "make_request", request)
    with i18n.context(), i18n.use_locale("ru"), i18n.use_theme(Theme.BASIC):
        yield SimpleNamespace(message=message, callback=callback, request=request)


async def test_theme_defaults_persists_and_profile_refresh_preserves_other_preferences(session):
    repository = UserRepository(session)
    service = ThemeService(repository)
    assert await service.get_theme(976001) == Theme.BASIC
    await service.set_theme(976001, Theme.HALLOWEEN)
    assert await repository.get_by_id(976001) is None

    # Raw INSERT proves the server default, independent of SQLAlchemy's Python default.
    await session.execute(text("INSERT INTO users (id, full_name) VALUES (976001, 'Student')"))
    user = await repository.get_by_id(976001)
    assert user.theme == "basic"
    user.locale, user.student_number, user.encrypted_password = "tr", "123", "encrypted"
    await service.set_theme(976001, Theme.HALLOWEEN)
    await session.flush()
    session.expire_all()
    assert await ThemeService(UserRepository(session)).get_theme(976001) == Theme.HALLOWEEN
    user = await repository.upsert(976001, "New name", "new_username")
    assert (user.theme, user.locale, user.student_number, user.encrypted_password) == (
        "halloween",
        "tr",
        "123",
        "encrypted",
    )
    other = await repository.upsert(976002, "Other", None)
    await session.flush()
    assert other.theme == "basic"
    assert await service.get_theme(976002) == Theme.BASIC
    await service.set_theme(976001, Theme.BASIC)
    await session.flush()
    session.expire_all()
    assert await service.get_theme(976001) == Theme.BASIC


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("selected", list(Theme))
async def test_theme_picker_selection_refreshes_menu_in_selected_theme(context, locale, selected):
    service = AsyncMock(spec=ThemeService)
    service.get_theme.return_value = Theme.BASIC
    with i18n.use_locale(locale.value):
        buttons = [button for row in build_settings_keyboard().inline_keyboard for button in row]
        assert SettingsCallback(action=SettingsAction.OPEN_THEME).pack() in [b.callback_data for b in buttons]
        await theme.on_open_theme(context.callback, service)
        service.get_theme.assert_awaited_once_with(976001)
        picker = context.request.await_args_list[0].args[1]
        assert [
            ThemeCallback.unpack(row[0].callback_data).theme for row in picker.reply_markup.inline_keyboard[:2]
        ] == list(Theme)
        assert picker.reply_markup.inline_keyboard[0][0].text.startswith("✅ ")
        assert (
            picker.reply_markup.inline_keyboard[-1][0].callback_data
            == SettingsCallback(action=SettingsAction.BACK_TO_SETTINGS).pack()
        )
        context.request.reset_mock()

        await theme.on_theme_selected(context.callback, ThemeCallback(theme=selected), service)
        service.set_theme.assert_awaited_once_with(976001, selected)
        methods = [call.args[1] for call in context.request.await_args_list]
        with i18n.use_theme(selected):
            assert methods[0].text == i18n.gettext("theme.selected").format(theme=theme.theme_name(selected))
            assert methods[0].reply_markup.inline_keyboard[list(Theme).index(selected)][0].text.startswith("✅ ")
            assert methods[1].text == i18n.gettext("common.welcome")
            assert methods[1].reply_markup == build_main_keyboard()
            assert methods[1].text.startswith("🎃 ") == (selected == Theme.HALLOWEEN)
        assert i18n.gettext("common.welcome").startswith("🎃 ") is False


async def test_repeated_selection_does_not_edit_identical_message(context):
    service = AsyncMock(spec=ThemeService)
    selected = ThemeCallback(theme=Theme.HALLOWEEN)
    await theme.on_theme_selected(context.callback, selected, service)
    method = context.request.await_args_list[0].args[1]
    current = context.message.model_copy(update={"text": method.text, "reply_markup": method.reply_markup})
    callback = context.callback.model_copy(update={"message": current})
    context.request.reset_mock()
    await theme.on_theme_selected(callback, selected, service)
    assert [call.args[1].__api_method__ for call in context.request.await_args_list] == [
        "sendMessage",
        "answerCallbackQuery",
    ]


def test_theme_callbacks_reject_unknown_values_and_handlers_are_private():
    with pytest.raises(ValidationError):
        ThemeCallback.unpack("theme:unknown")
    for selected in Theme:
        assert ThemeCallback.unpack(ThemeCallback(theme=selected).pack()).theme == selected
    assert all(handler.flags["private_chat_only"] for handler in theme.router.callback_query.handlers)


@pytest.mark.parametrize("fails", [False, True])
async def test_middleware_reads_saved_theme_and_restores_context(session, context, fails):
    repository = UserRepository(session)
    await repository.upsert(976001, "Student", None)
    service = ThemeService(repository)
    await service.set_theme(976001, Theme.HALLOWEEN)
    dependencies = {LocaleService: LocaleService(repository), ThemeService: service}
    data = {
        CONTAINER_NAME: SimpleNamespace(get=AsyncMock(side_effect=dependencies.__getitem__)),
        "event_from_user": context.callback.from_user,
    }

    async def handler(event, payload):
        assert i18n.gettext("menu.food").startswith("🎃 ")
        if fails:
            raise RuntimeError("handler failed")
        return "handled"

    if fails:
        with pytest.raises(RuntimeError, match="handler failed"):
            await LocaleMiddleware()(handler, context.callback, data)
    else:
        assert await LocaleMiddleware()(handler, context.callback, data) == "handled"
    assert i18n.gettext("menu.food").startswith("🍉 ")


@pytest.mark.parametrize("active", list(Theme))
async def test_old_reply_keyboard_labels_remain_usable(context, active):
    for previous in Theme:
        with i18n.use_theme(previous):
            label = i18n.gettext("menu.settings")
        with i18n.use_theme(active):
            assert await TranslatedText("menu.settings")(context.message.model_copy(update={"text": label}))
            assert i18n.gettext("menu.food").startswith("🎃 ") == (active == Theme.HALLOWEEN)


async def test_theme_context_is_isolated_between_concurrent_users():
    async def render(selected):
        with i18n.use_theme(selected):
            await asyncio.sleep(0)
            return i18n.gettext("common.welcome", locale="en")

    themed, basic = await asyncio.gather(render(Theme.HALLOWEEN), render(Theme.BASIC))
    assert themed == "🎃 " + basic
    assert basic == "Welcome to Manashelper!"


async def test_theme_migration_preserves_existing_profile_on_upgrade_and_downgrade(session):
    migration = run_path(str(PROJECT_ROOT / "alembic/versions/8b8ec5f9757a_add_user_theme.py"))
    # A transaction-local temporary table shadows users without touching application data.
    await session.execute(text("CREATE TEMPORARY TABLE users (id bigint PRIMARY KEY, full_name text, locale text)"))
    await session.execute(text("INSERT INTO users VALUES (976001, 'Existing student', 'tr')"))

    def apply(connection, direction):
        with Operations.context(MigrationContext.configure(connection)):
            migration[direction]()

    connection = await session.connection()
    await connection.run_sync(apply, "upgrade")
    row = (await session.execute(text("SELECT full_name, locale, theme FROM users WHERE id=976001"))).one()
    assert tuple(row) == ("Existing student", "tr", "basic")
    await connection.run_sync(apply, "downgrade")
    row = (await session.execute(text("SELECT full_name, locale FROM users WHERE id=976001"))).one()
    assert tuple(row) == ("Existing student", "tr")
