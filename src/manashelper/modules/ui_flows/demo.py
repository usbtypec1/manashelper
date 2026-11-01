"""An admin-only transport exercise; it never submits or replaces survey answers."""

from ui_flows.domain.schema import FlowDocument

DEMO_FLOW_ID = "ui_flow_demo"


def demo_document() -> FlowDocument:
    def text(key: str) -> dict[str, object]:
        return {"kind": "catalog", "key": key}

    def button(id: str, key: str, target: str, assignments: dict[str, object] | None = None) -> dict[str, object]:
        return {"kind": "transition", "id": id, "label": text(key), "target": target, "assignments": assignments or {}}

    return FlowDocument.model_validate(
        {
            "schema_version": 1,
            "id": DEMO_FLOW_ID,
            "entry": "check",
            "fields": {"submitted": {"type": "boolean"}, "answer": {"type": "text"}, "show": {"type": "boolean"}},
            "nodes": [
                {
                    "kind": "action",
                    "id": "check",
                    "delegate": "student_questions.has_submitted",
                    "arguments": {"user_id": {"kind": "ref", "scope": "user", "field": "id"}},
                    "results": {"submitted": "submitted"},
                    "outcomes": {"success": "menu"},
                },
                {
                    "kind": "menu",
                    "id": "menu",
                    "text": [text("ui_flows.demo.intro")],
                    "keyboard": "reply",
                    "buttons": [
                        [button("form", "ui_flows.demo.form", "answer")],
                        [button("exit", "common.cancel", "cancel")],
                    ],
                },
                {
                    "kind": "input",
                    "id": "answer",
                    "text": [text("ui_flows.demo.prompt")],
                    "field": "answer",
                    "input_type": "text",
                    "max_length": 120,
                    "next": "confirm",
                    "error": text("ui_flows.demo.invalid"),
                    "buttons": [[button("cancel", "common.cancel", "cancel")]],
                },
                {
                    "kind": "menu",
                    "id": "confirm",
                    "text": [text("ui_flows.demo.confirm")],
                    "keyboard": "inline",
                    "buttons": [
                        [
                            button(
                                "yes", "student_questions.yes", "choice", {"show": {"kind": "literal", "value": True}}
                            ),
                            button(
                                "no", "student_questions.no", "choice", {"show": {"kind": "literal", "value": False}}
                            ),
                        ],
                        [button("back", "common.back_to_menu", "answer")],
                        [button("cancel", "common.cancel", "cancel")],
                    ],
                },
                {
                    "kind": "condition",
                    "id": "choice",
                    "branches": [
                        {
                            "when": {
                                "kind": "compare",
                                "left": {"kind": "ref", "scope": "data", "field": "show"},
                                "operator": "eq",
                                "right": {"kind": "literal", "value": True},
                            },
                            "target": "shown",
                        }
                    ],
                    "default": "done",
                },
                {
                    "kind": "end",
                    "id": "shown",
                    "status": "completed",
                    "text": [
                        {
                            **text("ui_flows.demo.result"),
                            "parameters": {"answer": {"kind": "ref", "scope": "data", "field": "answer"}},
                        }
                    ],
                },
                {"kind": "end", "id": "done", "status": "completed", "text": [text("ui_flows.completed")]},
                {"kind": "end", "id": "cancel", "status": "cancelled", "text": [text("ui_flows.cancelled")]},
            ],
        }
    )
