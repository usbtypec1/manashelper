"""Export/check static gettext ownership and the PO import contracts, without a bot or DB."""

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

from babel.messages.pofile import read_po

from manashelper.platform.i18n.seed import LOCALES, REPLY_KEYS, import_document

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("features/ui_flows/text_inventory.json")


def owner(path: str) -> str:
    if "/modules/" in path:
        return path.split("/modules/", 1)[1].split("/", 1)[0]
    return "localization" if "/localization/" in path else "telegram"


def callsites(root: Path) -> list[dict[str, Any]]:
    result = []
    for source in sorted((root / "src/manashelper").rglob("*.py")):
        path = source.relative_to(root).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module and "i18n" in statement.module:
                for imported in statement.names:
                    if imported.name in {"gettext", "ngettext", "lazy_gettext"}:
                        aliases[imported.asname or imported.name] = imported.name
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            method = aliases.get(ast.unparse(node.func))
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"gettext", "ngettext"}:
                method = node.func.attr
            if method is None:
                continue
            key = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
            parameters = []
            parent = parents.get(node)
            if isinstance(parent, ast.Attribute) and parent.attr == "format":
                formatting = parents.get(parent)
                if isinstance(formatting, ast.Call):
                    parameters = sorted(keyword.arg for keyword in formatting.keywords if keyword.arg)
            scope = "admin" if path.endswith(("/editor_copy.py", "/web/landing.py")) else "user"
            result.append(
                {
                    "path": path,
                    "line": node.lineno,
                    "owner": owner(path),
                    "scope": scope,
                    "method": method,
                    "key": key if isinstance(key, str) else None,
                    "arguments": [ast.unparse(argument) for argument in node.args],
                    "format_parameters": parameters,
                }
            )
    return sorted(result, key=lambda item: (item["path"], item["line"]))


def inventory(root: Path) -> dict[str, Any]:
    document = import_document(root / "src/manashelper/locales")
    calls = callsites(root)
    catalogs = {}
    for locale in LOCALES:
        path = root / f"src/manashelper/locales/{locale}/LC_MESSAGES/messages.po"
        with path.open(encoding="utf-8") as stream:
            catalog = read_po(stream, locale=locale)
        messages = [message for message in catalog if message.id]
        catalogs[locale] = {
            "message_count": len(messages),
            "fuzzy_count": sum("fuzzy" in message.flags for message in messages),
            "nplurals": catalog.num_plurals,
            "legacy_plural_expression": catalog.plural_expr,
        }
    theme_source = ast.parse((root / "src/manashelper/platform/i18n/themes.py").read_text(encoding="utf-8"))
    icons = next(
        ast.literal_eval(node.value)
        for node in theme_source.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_HALLOWEEN_ICONS" for target in node.targets)
    )
    theme_targets = sorted(
        {
            node.args[0].value
            for node in ast.walk(theme_source)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
    )
    return {
        "version": 1,
        "user_key_count": len(document.entries),
        "excluded_admin_prefixes": ["ui_flows.editor.", "ui_flows.web."],
        "source_catalogs": catalogs,
        "keys": [
            {
                "key": entry.key,
                "owner": entry.owner,
                "parameters": list(entry.parameters),
                "content_type": entry.content_type,
                "plural_key": entry.plural_key,
            }
            for entry in document.entries
        ],
        "call_count": len(calls),
        "methods": dict(sorted(Counter(call["method"] for call in calls).items())),
        "calls": calls,
        "reply_keys": sorted(REPLY_KEYS),
        "commands": {
            path.relative_to(root).as_posix(): json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((root / "docs/commands").glob("*.json"))
        },
        "themes": {
            "icon_overrides": icons,
            "explicit_target_keys": theme_targets,
            "import_rule": "Materialize current theme results in each immutable release; do not decorate twice",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / OUTPUT
    serialized = json.dumps(inventory(ROOT), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != serialized:
            raise SystemExit(f"Text inventory is outdated: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")
    print(f"{'Checked' if args.check else 'Exported'} {OUTPUT}")


if __name__ == "__main__":
    main()
