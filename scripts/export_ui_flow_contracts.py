"""Export schema artifacts, or verify that committed copies match Python contracts."""

import argparse
import json
from pathlib import Path

from manashelper.modules.ui_flows.presentation.openapi import build_openapi
from ui_flows.domain.schema import FlowDocument


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "features" / "ui_flows"
    documents = {"flow.schema.json": FlowDocument.model_json_schema(), "openapi.json": build_openapi()}
    for name, document in documents.items():
        if name == "flow.schema.json":
            document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = root / name
        serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != serialized:
                raise SystemExit(f"Contract artifact is outdated: {path}")
        else:
            root.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized, encoding="utf-8")
        print(f"{'Checked' if args.check else 'Exported'} {name}")


if __name__ == "__main__":
    main()
