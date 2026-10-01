import re
from datetime import datetime
from pathlib import Path
from string import Formatter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import BotCommandScopeChat, Message
from babel.messages.extract import extract_from_dir
from babel.messages.frontend import parse_mapping_cfg
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from manashelper.bot.callback_data import LocaleCallback
from manashelper.bot.commands import setup_commands
from manashelper.bot.filters.translated_text import TranslatedText
from manashelper.bot.keyboards.locale import build_locale_keyboard, native_language_name
from manashelper.bot.routers.start import build_main_keyboard
from manashelper.localization.i18n import CatalogI18n, i18n
from manashelper.localization.locale import DEFAULT_LOCALE, Locale, resolve_from_language_code
from manashelper.services.bot_commands import build_admin_commands, build_group_commands, build_private_commands
from manashelper.services.locale import LocaleService

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "src/manashelper/locales"
KEY_PATTERN = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+")


@pytest.mark.parametrize("admin_chat_id", [0, 123_456])
async def test_command_registration_allows_local_start_without_admin_chat(admin_chat_id: int) -> None:
    bot = AsyncMock()
    settings = SimpleNamespace(admin_chat_id=admin_chat_id)
    await setup_commands(bot, settings)
    admin_calls = [
        call for call in bot.set_my_commands.await_args_list if isinstance(call.kwargs["scope"], BotCommandScopeChat)
    ]
    assert len(admin_calls) == int(bool(admin_chat_id))
    if admin_chat_id:
        assert admin_calls[0].kwargs["scope"].chat_id == admin_chat_id
    assert bot.set_my_commands.await_count == len(Locale) * 2 + 2 + int(bool(admin_chat_id))


def _catalog(locale: Locale):
    with (LOCALES_DIR / locale.value / "LC_MESSAGES/messages.po").open("rb") as file:
        return read_po(file, locale=locale.value)


def _placeholders(text: str) -> set[str]:
    return {field for _, field, _, _ in Formatter().parse(text) if field is not None}


@pytest.mark.parametrize("locale", list(Locale))
def test_catalogs_cover_every_key_and_preserve_placeholders(locale: Locale) -> None:
    english = _catalog(Locale.EN)
    catalog = _catalog(locale)
    assert {message.id for message in catalog} == {message.id for message in english}
    assert not catalog.fuzzy
    for message in catalog:
        if not message.id:
            continue
        keys = message.id if isinstance(message.id, tuple) else (message.id,)
        assert all(KEY_PATTERN.fullmatch(key) for key in keys), keys
        assert "fuzzy" not in message.flags, message.id
        source = english.get(message.id).string
        source_forms = source if isinstance(source, tuple) else (source,)
        forms = message.string if isinstance(message.string, tuple) else (message.string,)
        if isinstance(message.id, tuple):
            assert len(forms) == catalog.num_plurals
        expected_fields = _placeholders(source_forms[0])
        for translation in forms:
            assert translation and translation not in keys, (locale, message.id)
            assert _placeholders(translation) == expected_fields, (locale, message.id)


def test_babel_extracts_all_catalog_keys_including_command_descriptions() -> None:
    with (ROOT / "babel.cfg").open() as file:
        method_map, options_map = parse_mapping_cfg(file)
    extracted = {message for _, _, message, _, _ in extract_from_dir(ROOT, method_map, options_map)}
    assert extracted == {message.id for message in _catalog(Locale.EN) if message.id}


@pytest.mark.parametrize(
    ("language_code", "expected"),
    [
        ("zh", Locale.ZH),
        ("zh-CN", Locale.ZH),
        ("zh-Hans", Locale.ZH),
        ("zh-TW", Locale.ZH),
        ("ZH-Hant-HK", Locale.ZH),
        ("en-US", Locale.EN),
        ("ru-RU", Locale.RU),
        (None, DEFAULT_LOCALE),
        ("de", DEFAULT_LOCALE),
    ],
)
def test_language_detection(language_code: str | None, expected: Locale) -> None:
    assert resolve_from_language_code(language_code) == expected


def test_language_picker_shows_native_names_in_every_locale() -> None:
    for locale in Locale:
        with i18n.context(), i18n.use_locale(locale.value):
            buttons = [button for row in build_locale_keyboard().inline_keyboard for button in row]
            assert [button.text for button in buttons] == [
                "🇰🇬 Кыргызча",
                "🇷🇺 Русский",
                "🇬🇧 English",
                "🇹🇷 Türkçe",
                "🇨🇳 中文",
            ]
            assert [LocaleCallback.unpack(button.callback_data).locale for button in buttons] == list(Locale)
            assert native_language_name(Locale.ZH) == "中文"
            assert "请选择语言" in i18n.gettext("language.prompt")


@pytest.mark.parametrize("locale", list(Locale))
async def test_translated_reply_keyboard_buttons_match_filters(locale: Locale) -> None:
    keys = ["menu.food", "menu.schedule", "menu.attendance", "menu.grades", "menu.marketplace", "menu.settings"]
    with i18n.context(), i18n.use_locale(locale.value):
        labels = [button.text for row in build_main_keyboard().keyboard for button in row]
        assert labels == [i18n.gettext(key) for key in keys]
        for key, label in zip(keys, labels, strict=True):
            message = Message(message_id=1, date=datetime.now(), chat={"id": 1, "type": "private"}, text=label)
            assert await TranslatedText(key)(message)
            unrelated = message.model_copy(update={"text": "unrelated message"})
            assert not await TranslatedText(key)(unrelated)


@pytest.mark.parametrize("locale", list(Locale))
def test_command_descriptions_use_requested_locale(locale: Locale) -> None:
    with i18n.context(), i18n.use_locale(Locale.RU.value):
        for build_commands in (build_private_commands, build_group_commands, build_admin_commands):
            for command in build_commands(locale):
                assert command.description == i18n.gettext(f"commands.{command.command}", locale=locale.value)
                assert not KEY_PATTERN.fullmatch(command.description)
                assert 1 <= len(command.description) <= 256
    chinese = {command.command: command.description for command in build_private_commands(Locale.ZH)}
    assert chinese["start"] == "启动机器人"
    assert chinese["language"] == "更改语言"


@pytest.mark.parametrize("locale", list(Locale))
def test_only_group_yemek_command_is_ephemeral(locale: Locale) -> None:
    group = {command.command: command for command in build_group_commands(locale)}
    assert group["yemek"].is_ephemeral is True
    assert group["versions"].is_ephemeral is None
    assert all(command.is_ephemeral is None for command in build_private_commands(locale))


def test_missing_translations_fall_back_to_english_catalog(tmp_path: Path) -> None:
    for locale in (Locale.EN, Locale.RU):
        catalog = _catalog(locale)
        if locale == Locale.RU:
            catalog.delete("common.welcome")
            catalog.delete("obis.skips_left.one")
        path = tmp_path / locale.value / "LC_MESSAGES/messages.mo"
        path.parent.mkdir(parents=True)
        with path.open("wb") as file:
            write_mo(file, catalog)
    translations = CatalogI18n(path=tmp_path, default_locale=Locale.RU.value)
    assert translations.gettext("common.welcome") == "Welcome to Manashelper!"
    assert translations.gettext("obis.skips_left.one", "obis.skips_left.many", 1) == "{count} skip left"
    assert translations.gettext("obis.skips_left.one", "obis.skips_left.many", 2) == "{count} skips left"
    assert translations.gettext("common.welcome", locale="de") == "Welcome to Manashelper!"
    assert translations.gettext("common.welcome", locale="en") == "Welcome to Manashelper!"


@pytest.mark.parametrize(
    ("locale", "count", "expected"),
    [
        (Locale.EN, 1, "1 skip left"),
        (Locale.EN, 2, "2 skips left"),
        (Locale.RU, 1, "осталось 1 пропуск"),
        (Locale.RU, 2, "осталось 2 пропуска"),
        (Locale.RU, 5, "осталось 5 пропусков"),
        (Locale.ZH, 0, "还可缺勤 0 次"),
        (Locale.ZH, 1, "还可缺勤 1 次"),
        (Locale.ZH, 5, "还可缺勤 5 次"),
    ],
)
def test_plural_forms(locale: Locale, count: int, expected: str) -> None:
    text = i18n.gettext("obis.skips_left.one", "obis.skips_left.many", count, locale=locale.value)
    assert text.format(count=count) == expected


async def test_chinese_locale_is_detected_saved_and_keeps_manual_selection() -> None:
    user = SimpleNamespace(locale=None)
    repository = AsyncMock()
    repository.upsert.return_value = user
    repository.get_by_id.return_value = user
    service = LocaleService(repository)
    assert await service.resolve(1, "Student", None, "zh-CN") == Locale.ZH
    assert user.locale == "zh"
    assert await service.get_locale(1) == Locale.ZH
    assert await service.resolve(1, "Student", None, "en") == Locale.ZH
    await service.set_locale(1, Locale.ZH)
    repository.set_locale.assert_awaited_once_with(1, "zh")
