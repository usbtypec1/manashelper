import ast
import json

from manashelper.modules.ui_flows.presentation.openapi import build_openapi
from tests.paths import PROJECT_ROOT
from ui_flows.domain.schema import FlowDocument

CONTRACTS = PROJECT_ROOT / "features/ui_flows"


def test_committed_contracts_match_the_python_source():
    expected = FlowDocument.model_json_schema()
    expected["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    assert json.loads((CONTRACTS / "flow.schema.json").read_text(encoding="utf-8")) == expected
    assert json.loads((CONTRACTS / "openapi.json").read_text(encoding="utf-8")) == build_openapi()


def test_openapi_references_resolve_and_mutations_require_session_and_csrf():
    spec = build_openapi()

    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                parts = value["$ref"].removeprefix("#/").split("/")
                target = spec
                for part in parts:
                    target = target[part]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    check_refs(spec)
    ids = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            ids.append(operation["operationId"])
            if path in {"/auth/exchange", "/auth/telegram"}:
                assert operation["security"] == []
            elif method == "get":
                assert operation["security"] == [{"AdminSession": []}, {"MiniAppBearer": []}]
            else:
                assert operation["security"] == [{"AdminSession": [], "CsrfToken": []}, {"MiniAppBearer": []}]
    assert len(ids) == len(set(ids))


def test_catalog_keys_are_literal_and_exist_in_all_source_catalogs():
    source = PROJECT_ROOT / "src/manashelper/modules/ui_flows/catalog.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    keys = {
        call.args[0].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "_"
        and call.args
        and isinstance(call.args[0], ast.Constant)
    }
    assert keys
    for locale in ("en", "ru", "ky", "tr", "zh"):
        catalog = PROJECT_ROOT / f"src/manashelper/locales/{locale}/LC_MESSAGES/messages.po"
        content = catalog.read_text(encoding="utf-8")
        assert all(f'msgid "{key}"' in content for key in keys)


def test_missing_target_issue_locates_the_exact_button(main_menu_document, validate_document):
    main_menu_document["nodes"][0]["buttons"][0][0]["target"] = "missing"
    issue = next(issue for issue in validate_document(main_menu_document) if issue.code == "missing_target")
    assert issue.path == "/nodes/0/buttons/0/0/target"
    assert issue.node_id == "main"
    assert issue.button_id == "food"
