import runpy
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Message

from manashelper.localization.i18n import i18n
from manashelper.modules.versions import history
from manashelper.modules.versions import router as handlers
from manashelper.modules.versions.callbacks import VersionCallback, VersionsPageCallback
from manashelper.modules.versions.formatter import format_version_detail, format_versions_list_header
from manashelper.modules.versions.keyboards import build_version_detail_keyboard, build_versions_list_keyboard


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "VERSIONS_DIR", tmp_path)
    for patch in range(11):
        (tmp_path / f"2.0.{patch}-2026-10-01.md").write_text(
            f"  <b>Release {patch}</b>\n\nContent & details  ", encoding="utf-8"
        )
    with i18n.context(), i18n.use_locale("en"):
        yield tmp_path


def test_runtime_versions_path_points_to_repository():
    assert Path(__file__).resolve().parents[1] / "docs" / "versions" == history.VERSIONS_DIR
    assert history.VERSIONS_DIR.is_dir()
    assert history.get_page(0)


def test_runtime_path_preserved_in_docker_like_layout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = Path(history.__file__).resolve()
    app = tmp_path / "app"
    copied_module = app / source.relative_to(root)
    copied_module.parent.mkdir(parents=True)
    copied_module.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    namespace = runpy.run_path(str(copied_module))
    assert namespace["VERSIONS_DIR"] == app / "docs" / "versions"


def test_missing_directory_returns_empty_catalog(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "VERSIONS_DIR", tmp_path / "missing")
    assert history.total_pages() == 1
    assert history.get_page(0) == []
    assert history.get_version("2.0.0") is None


def test_catalog_uses_numeric_version_order_and_ten_entry_pages(catalog):
    assert history.total_pages() == 2
    assert [entry.version for entry in history.get_page(0)] == [f"2.0.{patch}" for patch in range(10, 0, -1)]
    assert [entry.version for entry in history.get_page(1)] == ["2.0.0"]
    assert history.get_page(2) == []
    assert all(entry.released_at == date(2026, 10, 1) for entry in history.get_page(0))


def test_invalid_dates_missing_separator_and_non_markdown_files_are_ignored(catalog):
    for name in ("README.md", "8.0.0-invalid-date.md", "9.0.0-2026-99-99.md", "10.0.0-2026-10-01.txt"):
        (catalog / name).write_text("Ignored", encoding="utf-8")
    assert sum(len(history.get_page(page)) for page in range(history.total_pages())) == 11
    assert history.get_version("9.0.0") is None


def test_file_additions_and_edits_are_read_without_restart(catalog):
    detail = history.get_version("2.0.0")
    assert detail.description == "<b>Release 0</b>\n\nContent & details"
    (catalog / "2.0.0-2026-10-01.md").write_text("Updated", encoding="utf-8")
    assert history.get_version("2.0.0").description == "Updated"
    (catalog / "3.0.0-2026-10-25.md").write_text("New release", encoding="utf-8")
    assert history.get_page(0)[0].version == "3.0.0"


@pytest.mark.parametrize("locale", ["en", "ru", "ky", "tr", "zh"])
def test_formatter_preserves_release_body_and_localizes_headers(locale):
    detail = history.VersionDetail("2.0.0", date(2026, 10, 1), "<b>Release</b>\nContent & details")
    with i18n.context(), i18n.use_locale(locale):
        text = format_version_detail(detail)
        assert text.endswith("<b>Release</b>\nContent & details")
        assert "01.10.2026" in text and "2.0.0" in text
        assert format_versions_list_header(0, 1) == i18n.gettext("versions.title")
        assert format_versions_list_header(1, 3) == i18n.gettext("versions.title_page").format(page=2, total_pages=3)


def test_keyboards_preserve_rows_and_navigation_payloads(catalog):
    assert VersionCallback(version="2.0.10", page=1).pack() == "version:2.0.10:1"
    assert VersionsPageCallback(page=2).pack() == "versions_page:2"
    keyboard = build_versions_list_keyboard(history.get_page(0), 1, 3)
    assert [len(row) for row in keyboard.inline_keyboard] == [4, 4, 2, 2]
    assert [button.callback_data for button in keyboard.inline_keyboard[-1]] == ["versions_page:0", "versions_page:2"]
    assert build_version_detail_keyboard(1).inline_keyboard[0][0].callback_data == "versions_page:1"


async def test_command_and_page_navigation_keep_same_messages(catalog):
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    message.edit_text = AsyncMock()
    await handlers.cmd_versions(message)
    assert message.answer.await_args.args[0] == format_versions_list_header(0, 2)
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.message = message
    await handlers.on_versions_page_selected(callback, VersionsPageCallback(page=1))
    edited = message.edit_text.await_args
    assert edited.args[0] == format_versions_list_header(1, 2)
    assert edited.kwargs["reply_markup"].inline_keyboard[0][0].text == "v2.0.0"
    callback.answer.assert_awaited_once()


async def test_detail_navigation_reads_entry_and_unknown_version_only_answers_callback(catalog):
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    await handlers.on_version_selected(callback, VersionCallback(version="2.0.10", page=1))
    edited = callback.message.edit_text.await_args
    assert edited.args[0] == format_version_detail(history.get_version("2.0.10"))
    assert edited.kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "versions_page:1"
    callback.message.edit_text.reset_mock()
    await handlers.on_version_selected(callback, VersionCallback(version="missing", page=1))
    callback.message.edit_text.assert_not_awaited()
    assert callback.answer.await_count == 2
