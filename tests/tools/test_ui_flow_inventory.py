import copy
import json
from pathlib import Path

import pytest

from scripts.check_ui_flow_inventory import INVENTORY, check_inventory, source_facts
from tests.paths import PROJECT_ROOT

SOURCE = """
from aiogram import Router, flags
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router(name="sample")
RESULTS_KEY = "saved_pages"
DEEP_LINK_PAYLOAD_PREFIX = "sample_"

class Form(StatesGroup):
    query = State()

class Page(CallbackData, prefix="page"):
    index: int

@router.message(CommandStart(deep_link=True))
@flags.private_chat_only
async def search(message, state: FSMContext):
    await state.update_data({RESULTS_KEY: []})
    data = await state.get_data()
    return data.get(RESULTS_KEY)

async def show_results(message):
    pass

router.message.register(show_results, Command("results"))
"""


def fixture_matrix(root: Path):
    return {
        "version": 1,
        "groups": [
            {
                "id": "sample",
                "owner": "modules/sample",
                "target_scenarios": ["sample.search"],
                "invariants": ["Private"],
            }
        ],
        "items": [dict(item, group="sample", targets=["sample.search"]) for item in source_facts(root)],
    }


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "src/manashelper/modules/sample/presentation/router.py"
    path.parent.mkdir(parents=True)
    path.write_text(SOURCE, encoding="utf-8")
    return path


def test_committed_matrix_covers_current_source():
    inventory = json.loads((PROJECT_ROOT / INVENTORY).read_text(encoding="utf-8"))
    assert check_inventory(PROJECT_ROOT, inventory) == []


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('name="sample"', 'name="renamed"'),
        ("@flags.private_chat_only", "@flags.preserve_ui_flow"),
        ('prefix="page"', 'prefix="new_page"'),
        ('"sample_"', '"changed_"'),
        ('"saved_pages"', '"other_pages"'),
        ("query = State()", "query = State()\n    confirm = State()"),
        ("state.update_data({RESULTS_KEY: []})", "state.update_data({RESULTS_KEY: [], 'new_key': 1})"),
        ("data.get(RESULTS_KEY)", "data.get('other_key')"),
        ("deep_link=True", "deep_link=False"),
        ('Command("results")', 'Command("other")'),
        ("async def show_results", "async def renamed_presenter"),
    ],
)
def test_source_changes_require_matrix_review(tmp_path, source, before, after):
    matrix = fixture_matrix(tmp_path)
    source.write_text(SOURCE.replace(before, after), encoding="utf-8")
    assert check_inventory(tmp_path, matrix)


def test_added_handler_and_explicit_registration_are_not_silently_covered(tmp_path, source):
    matrix = fixture_matrix(tmp_path)
    source.write_text(
        SOURCE + "\n@router.callback_query(Page.filter())\nasync def page(callback):\n    pass\n"
        'router.message.register(page, Command("second"))\n',
        encoding="utf-8",
    )
    errors = check_inventory(tmp_path, matrix)
    assert any("Unmapped source:" in error and "::page::handler" in error for error in errors)
    assert any("register#2::registration" in error for error in errors)


def test_command_menu_change_requires_review(tmp_path, source):
    matrix = fixture_matrix(tmp_path)
    commands = tmp_path / "docs/commands/private.json"
    commands.parent.mkdir(parents=True)
    commands.write_text('[{"command":"sample","description":"commands.sample"}]', encoding="utf-8")
    assert any("::sample::command" in error for error in check_inventory(tmp_path, matrix))


def test_dispatch_order_and_feature_handoff_guards_require_review(tmp_path, source):
    dispatcher = tmp_path / "src/manashelper/platform/telegram/dispatcher.py"
    dispatcher.parent.mkdir(parents=True)
    dispatcher.write_text("dispatcher.include_routers(survey_router, start_router)", encoding="utf-8")
    menus = tmp_path / "src/manashelper/modules/ui_flows/menus.py"
    menus.parent.mkdir(parents=True)
    menus.write_text("FEATURES = frozenset({'eders'})\nEDERS_FEATURES = frozenset({'eders'})", encoding="utf-8")
    matrix = fixture_matrix(tmp_path)
    dispatcher.write_text("dispatcher.include_routers(start_router, survey_router)", encoding="utf-8")
    menus.write_text(
        "FEATURES = frozenset({'eders', 'food_menu'})\nEDERS_FEATURES = frozenset(set())", encoding="utf-8"
    )
    errors = check_inventory(tmp_path, matrix)
    assert any("include_routers::dispatch_order" in error for error in errors)
    assert any("food_menu::feature_handoff" in error for error in errors)
    assert any("eders::feature_handoff" in error for error in errors)


def test_matrix_rejects_missing_owner_target_duplicate_and_removed_surface(tmp_path, source):
    matrix = fixture_matrix(tmp_path)
    invalid = copy.deepcopy(matrix)
    invalid["groups"][0]["owner"] = ""
    invalid["items"][0]["targets"] = ["undefined"]
    invalid["items"].append(invalid["items"][0])
    source.write_text("", encoding="utf-8")
    errors = check_inventory(tmp_path, invalid)
    assert any("Incomplete owner" in error for error in errors)
    assert any("Missing/invalid owner or target" in error for error in errors)
    assert any("Duplicate item" in error for error in errors)
    assert any("Removed source" in error for error in errors)


def test_comments_and_line_offsets_do_not_invalidate_matrix(tmp_path, source):
    matrix = fixture_matrix(tmp_path)
    source.write_text("# Shifted source; source locations are not contracts.\n\n" + SOURCE, encoding="utf-8")
    assert check_inventory(tmp_path, matrix) == []
