"""Check the authored UI migration matrix against Python source without importing the bot.

--scan prints current source facts for reviewing/updating the matrix. It never assigns
owners or target scenarios: those decisions belong to the authored inventory.
"""

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = Path("features/ui_flows/inventory.json")
OBSERVER_NAMES = {"message", "callback_query", "edited_message", "inline_query", "chosen_inline_result"}
FLAT_UI_FILES = {"router.py", "callbacks.py", "keyboards.py", "sender.py", "formatter.py", "entrypoints.py"}
# These are HTTP/editor contracts, not Telegram presenters. They stay covered by
# their own exported contracts and API/E2E tests during the later HTTP migration.
EDITOR_FILES = {"admin_router.py", "admin_provider.py", "admin_contracts.py", "openapi.py", "editor_copy.py"}


def expression(node: ast.AST) -> str:
    return ast.unparse(node)


def is_presenter(path: str) -> bool:
    name = Path(path).name
    if path in {
        "src/manashelper/modules/broadcast/content.py",
        "src/manashelper/platform/telegram/command_catalog.py",
        "src/manashelper/platform/web/login.py",
    }:
        return True
    if "/modules/" in path:
        return ("/presentation/" in path and name not in EDITOR_FILES) or name in FLAT_UI_FILES
    return path.startswith("src/manashelper/platform/telegram/") and (
        "/keyboards/" in path or name in {"navigation.py", "entrypoints.py"}
    )


def functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    result = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append((node.name, node))
        elif isinstance(node, ast.ClassDef):
            result.extend(
                (f"{node.name}.{child.name}", child)
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name != "__init__"
            )
    return result


def fsm_calls(node: ast.AST) -> list[str]:
    # Both direct FSMContext parameters and TelegramFlowContext.state handoffs.
    return sorted(
        {
            expression(call)
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in {"clear", "get_state", "set_state", "get_data", "set_data", "update_data"}
            and (expression(call.func.value) == "state" or expression(call.func.value).endswith(".state"))
        }
    )


def fsm_reads(node: ast.AST) -> list[str]:
    aliases: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AnnAssign)) and child.value is not None:
            value = child.value.value if isinstance(child.value, ast.Await) else child.value
            if isinstance(value, ast.Call) and expression(value).endswith("state.get_data()"):
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                aliases.update(expression(target) for target in targets)
    reads = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Subscript) and (
            expression(child.value) in aliases or "state.get_data()" in expression(child.value)
        ):
            reads.add(expression(child))
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr == "get" and expression(child.func.value) in aliases:
                reads.add(expression(child))
        elif isinstance(child, ast.Compare) and any(expression(part) in aliases for part in child.comparators):
            reads.add(expression(child))
    return sorted(reads)


def source_facts(root: Path) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    def add(path: str, symbol: str, kind: str, **details: Any) -> None:
        facts.append({"path": path, "symbol": symbol, "kind": kind, **details})

    for source in sorted((root / "src/manashelper").rglob("*.py")):
        path = source.relative_to(root).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"))
        routers = {
            target.id
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and expression(node.value.func) in {"Router", "aiogram.Router"}
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("aiogram.fsm"):
                add(path, node.module or "", "fsm_dependency", definition=expression(node))
            elif isinstance(node, ast.Assign) and any(expression(target) in routers for target in node.targets):
                add(path, expression(node.targets[0]), "router", definition=expression(node.value))
            elif isinstance(node, ast.ClassDef):
                bases = {expression(base).split(".")[-1] for base in node.bases}
                if bases & {"StatesGroup", "CallbackData"}:
                    add(
                        path,
                        node.name,
                        "states" if "StatesGroup" in bases else "callback",
                        definition=expression(node),
                    )
                elif Path(path).name == "callbacks.py":
                    add(path, node.name, "callback_values", definition=expression(node))
        for symbol, node in functions(tree):
            bindings = [
                expression(decorator)
                for decorator in node.decorator_list
                if isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in OBSERVER_NAMES
                and expression(decorator.func.value) in routers
            ]
            calls = fsm_calls(node)
            if not (bindings or calls or is_presenter(path)):
                continue
            details: dict[str, Any] = {}
            if bindings:
                # Include privacy/masking/runtime flags as well as entry filters.
                details["bindings"] = [expression(decorator) for decorator in node.decorator_list]
            if calls:
                details["fsm_calls"] = calls
                details["fsm_reads"] = fsm_reads(node)
            add(path, symbol, "handler" if bindings else "presenter", **details)
        if routers:
            # Explicit registration, observer-wide guards, and raw callback/payload
            # filters are preserved as source expressions rather than guessed routes.
            registrations: Counter[str] = Counter()
            for node in tree.body:
                if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                if isinstance(call.func, ast.Attribute) and call.func.attr in {"register", "filter"}:
                    receiver = expression(call.func.value)
                    if receiver.split(".")[0] in routers:
                        name = receiver + "." + call.func.attr
                        registrations[name] += 1
                        add(path, f"{name}#{registrations[name]}", "registration", definition=expression(call))
        if is_presenter(path) or routers:
            # Resolves the named cache keys used in FSM calls, including the keys
            # shared across router/entrypoint modules. No live form values are read.
            for node in tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if "KEY" in target.id:
                                add(path, target.id, "storage_key", value=node.value.value)
                            elif "PAYLOAD" in target.id or "PREFIX" in target.id:
                                add(path, target.id, "entry_constant", value=node.value.value)
        if path == "src/manashelper/platform/telegram/dispatcher.py":
            for descendant in ast.walk(tree):
                if isinstance(descendant, ast.Call) and expression(descendant.func) == "dispatcher.include_routers":
                    add(path, "include_routers", "dispatch_order", definition=expression(descendant))
        if path == "src/manashelper/modules/ui_flows/menus.py":
            feature_sets = {}
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    expression(target) in {"FEATURES", "EDERS_FEATURES"} for target in node.targets
                ):
                    add(path, expression(node.targets[0]), "feature_handoffs", definition=expression(node.value))
                    assert isinstance(node.value, ast.Call)
                    feature_sets[expression(node.targets[0])] = ast.literal_eval(node.value.args[0])
            for feature in sorted(feature_sets["FEATURES"]):
                add(path, feature, "feature_handoff", eders_enabled=feature in feature_sets["EDERS_FEATURES"])
    for source in sorted((root / "docs/commands").glob("*.json")):
        for command in json.loads(source.read_text(encoding="utf-8")):
            add(source.relative_to(root).as_posix(), command["command"], "command", **command)
    return sorted(facts, key=fact_id)


def fact_id(fact: dict[str, Any]) -> str:
    return f"{fact['path']}::{fact['symbol']}::{fact['kind']}"


def check_inventory(root: Path, inventory: dict[str, Any]) -> list[str]:
    errors = []
    if inventory.get("version") != 1:
        errors.append("Unsupported matrix version")
    groups = {group["id"]: group for group in inventory["groups"]}
    if len(groups) != len(inventory["groups"]):
        errors.append("Duplicate group ID")
    for group in groups.values():
        if not group.get("owner") or not group.get("target_scenarios") or not group.get("invariants"):
            errors.append(f"Incomplete owner/scenarios/invariants: {group['id']}")
    current = {fact_id(fact): fact for fact in source_facts(root)}
    authored = {}
    for item in inventory["items"]:
        key = fact_id(item)
        if key in authored:
            errors.append(f"Duplicate item: {key}")
        authored[key] = {field: value for field, value in item.items() if field not in {"group", "targets"}}
        group = groups.get(item.get("group"))
        if group is None or not item.get("targets") or not set(item["targets"]) <= set(group["target_scenarios"]):
            errors.append(f"Missing/invalid owner or target scenarios: {key}")
    for key in sorted(current.keys() - authored.keys()):
        errors.append(f"Unmapped source: {key}")
    for key in sorted(authored.keys() - current.keys()):
        errors.append(f"Removed source still in matrix: {key}")
    for key in sorted(current.keys() & authored.keys()):
        if current[key] != authored[key]:
            errors.append(f"Changed source contract: {key}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true", help="Print unassigned source facts; does not modify the matrix")
    parser.add_argument("--check", action="store_true", help="Verify source coverage (the default)")
    args = parser.parse_args()
    if args.scan:
        print(json.dumps(source_facts(ROOT), ensure_ascii=False, indent=2))
        return
    inventory = json.loads((ROOT / INVENTORY).read_text(encoding="utf-8"))
    errors = check_inventory(ROOT, inventory)
    if errors:
        raise SystemExit("UI migration matrix is stale:\n" + "\n".join(errors))
    counts = Counter(item["kind"] for item in inventory["items"])
    print(f"Checked {len(inventory['items'])} UI surfaces in {len(inventory['groups'])} groups: {dict(counts)}")


if __name__ == "__main__":
    main()
