"""Initial food notification scenario; database publications remain authoritative."""

from manashelper.modules.food_menu.ui_delegates import CLEANUP_OPTIONS, DAY_ROWS
from ui_flows.domain.schema import (
    ActionNode,
    Button,
    CatalogText,
    DataField,
    FlowDocument,
    InlineText,
    LiteralValue,
    MenuNode,
    ReferenceValue,
    RepeatedButtons,
    ReturnNode,
    TransitionButton,
    Value,
)


def _label(name: str) -> InlineText:
    return InlineText(
        kind="inline",
        translations={"en": "{value}"},
        parameters={"value": ReferenceValue(kind="ref", scope="item", field=name)},
    )


def _action(action: str, weekday: int = 0, meal: str = "") -> dict[str, Value]:
    return {
        "action": LiteralValue(kind="literal", value=action),
        "weekday": LiteralValue(kind="literal", value=weekday),
        "meal": LiteralValue(kind="literal", value=meal),
    }


def _static(identifier: str, key: str, *, action: str, meal: str = "") -> TransitionButton:
    return TransitionButton(
        kind="transition",
        id=identifier,
        label=CatalogText(kind="catalog", key=key),
        target="change",
        assignments=_action(action, meal=meal),
    )


def food_menu_notification_scenario() -> FlowDocument:
    row: list[Button] = []
    for identifier, label, action, meal in (
        ("weekday", "label", "weekday", ""),
        ("lunch", "lunch", "day", "lunch"),
        ("dinner", "dinner", "day", "dinner"),
    ):
        assignments = _action(action, meal=meal)
        values: dict[str, Value] = {
            **assignments,
            "weekday": ReferenceValue(kind="ref", scope="item", field="weekday"),
        }
        row.append(
            TransitionButton(kind="transition", id=identifier, label=_label(label), target="change", assignments=values)
        )
    return FlowDocument(
        schema_version=2,
        id="food_menu_notifications",
        entry="load",
        fields={
            "days": DAY_ROWS,
            "action": DataField(type="text"),
            "weekday": DataField(type="integer"),
            "meal": DataField(type="text"),
        },
        initial_data={"days": [], "action": "", "weekday": 0, "meal": ""},
        outcomes=["completed", "cancelled"],
        nodes=[
            ActionNode(
                kind="action",
                id="load",
                delegate="food_menu.notifications.read",
                results={"days": "days"},
                outcomes={"success": "menu"},
            ),
            MenuNode(
                kind="menu",
                id="menu",
                keyboard="inline",
                text=[CatalogText(kind="catalog", key="food.notification_settings")],
                buttons=[
                    [
                        _static("all_lunch", "food.lunch", action="meal", meal="lunch"),
                        _static("all_dinner", "food.dinner", action="meal", meal="dinner"),
                    ],
                    [
                        _static("enable_all", "common.enable_all", action="enable_all"),
                        _static("disable_all", "common.disable_all", action="disable_all"),
                    ],
                    [
                        TransitionButton(
                            kind="transition",
                            id="back",
                            label=CatalogText(kind="catalog", key="common.back"),
                            target="completed",
                        )
                    ],
                ],
                repeated=[RepeatedButtons(source=ReferenceValue(kind="ref", scope="data", field="days"), buttons=row)],
            ),
            ActionNode(
                kind="action",
                id="change",
                delegate="food_menu.notifications.change",
                arguments={
                    name: ReferenceValue(kind="ref", scope="data", field=name) for name in ("action", "weekday", "meal")
                },
                outcomes={"success": "load"},
            ),
            ReturnNode(kind="return", id="completed", outcome="completed"),
        ],
    )


def food_menu_cleanup_scenario() -> FlowDocument:
    return FlowDocument(
        schema_version=2,
        id="food_menu_cleanup",
        entry="load",
        fields={"options": CLEANUP_OPTIONS, "option": DataField(type="text")},
        initial_data={"options": [], "option": ""},
        outcomes=["completed"],
        nodes=[
            ActionNode(
                kind="action",
                id="load",
                delegate="food_menu.cleanup.read",
                results={"options": "options"},
                outcomes={"success": "menu"},
            ),
            MenuNode(
                kind="menu",
                id="menu",
                keyboard="inline",
                text=[CatalogText(kind="catalog", key="food.auto_delete_prompt")],
                buttons=[
                    [
                        TransitionButton(
                            kind="transition",
                            id="back",
                            label=CatalogText(kind="catalog", key="common.back"),
                            target="completed",
                        )
                    ]
                ],
                repeated=[
                    RepeatedButtons(
                        source=ReferenceValue(kind="ref", scope="data", field="options"),
                        buttons=[
                            TransitionButton(
                                kind="transition",
                                id="select",
                                label=_label("label"),
                                target="change",
                                assignments={"option": ReferenceValue(kind="ref", scope="item", field="id")},
                            )
                        ],
                    )
                ],
            ),
            ActionNode(
                kind="action",
                id="change",
                delegate="food_menu.cleanup.change",
                arguments={"option": ReferenceValue(kind="ref", scope="data", field="option")},
                outcomes={"success": "load"},
            ),
            ReturnNode(kind="return", id="completed", outcome="completed"),
        ],
    )
