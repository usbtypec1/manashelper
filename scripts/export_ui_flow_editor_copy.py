"""Export compiled gettext copy for the browser; --check detects stale bundles."""

import argparse
import json
from pathlib import Path

from manashelper.modules.ui_flows.presentation.editor_copy import get_editor_copy
from manashelper.platform.i18n.catalog import i18n


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    messages = {}
    with i18n.context(), i18n.use_locale("en"):
        messages["en"] = get_editor_copy()
    serialized = json.dumps(messages, ensure_ascii=False, indent=2) + "\n"
    path = Path(__file__).resolve().parents[1] / "src/admin-ui/src/generated/messages.json"
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != serialized:
            raise SystemExit("Editor translations are stale; compile catalogs and export editor copy")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
