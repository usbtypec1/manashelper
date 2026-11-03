"""Initial main/study menu document; later edits and versions belong to the DB."""

from typing import Any

from ui_flows.domain.schema import FlowDocument

MAIN_MENU_ID = "main_menu"
FEATURES = frozenset(
    {
        "food_menu",
        "marketplace",
        "settings",
        "notifications",
        "course_tracking",
        "obis_credentials",
        "phone_numbers",
        "feedback",
        "schedule",
        "study_week",
        "attendance",
        "grades",
        "eders",
        "eders_materials",
    }
)
EDERS_FEATURES = frozenset({"study_week", "eders", "eders_materials"})


def main_menu_document() -> FlowDocument:
    def text(key: str) -> dict[str, Any]:
        return {"kind": "catalog", "key": key}

    def button(id: str, key: str, target: str, *, eders: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": "transition", "id": id, "label": text(key), "target": target}
        if eders:
            result["when"] = {
                "kind": "compare",
                "left": {"kind": "ref", "scope": "capabilities", "field": "eders_enabled"},
                "operator": "eq",
                "right": {"kind": "literal", "value": True},
            }
        return result

    destinations = {
        "food": "food_menu",
        "marketplace": "marketplace",
        "settings": "settings",
        "schedule": "schedule",
        "week": "study_week",
        "attendance": "attendance",
        "grades": "grades",
        "eders": "eders",
        "materials": "eders_materials",
    }
    return FlowDocument.model_validate(
        {
            "schema_version": 2,
            "id": MAIN_MENU_ID,
            "entry": "main",
            "navigation_entries": {"study": "study"},
            "nodes": [
                {
                    "kind": "menu",
                    "id": "main",
                    "text": [text("common.welcome")],
                    "keyboard": "reply",
                    "buttons": [
                        [button("food", "menu.food", "food"), button("study", "menu.study", "study")],
                        [button("marketplace", "menu.marketplace", "marketplace")],
                        [button("settings", "menu.settings", "settings")],
                    ],
                },
                {
                    "kind": "menu",
                    "id": "study",
                    "text": [text("menu.study")],
                    "keyboard": "reply",
                    "buttons": [
                        [
                            button("schedule", "menu.schedule", "schedule"),
                            button("week", "menu.study_week", "week", eders=True),
                        ],
                        [
                            button("attendance", "menu.attendance", "attendance"),
                            button("grades", "menu.grades", "grades"),
                        ],
                        [
                            button("eders", "menu.eders", "eders", eders=True),
                            button("materials", "menu.eders_materials", "materials", eders=True),
                        ],
                        [button("back", "common.back_to_menu", "main")],
                    ],
                },
                *[
                    {
                        "kind": "call",
                        "id": node,
                        "flow": "settings",
                        "outcomes": {"completed": "main", "cancelled": "main"},
                    }
                    if feature == "settings"
                    else {"kind": "end", "id": node, "status": "handed_off", "feature": feature}
                    for node, feature in destinations.items()
                ],
            ],
            "layout": {
                "main": {"x": 60, "y": 80},
                "study": {"x": 390, "y": 80},
                **{
                    node: {"x": 750 + (index % 3) * 300, "y": 80 + (index // 3) * 230}
                    for index, node in enumerate(destinations)
                },
            },
        }
    )
