"""Initial notification settings scenario; published database versions are authoritative."""

from typing import Literal

from manashelper.modules.notifications.settings import NotificationSetting
from ui_flows.domain.schema import (
    ActionNode,
    Button,
    CallNode,
    CatalogText,
    Compare,
    DataField,
    EndNode,
    FlowDocument,
    InlineText,
    LiteralValue,
    MenuNode,
    Node,
    ReferenceValue,
    ReturnNode,
    TransitionButton,
)


def _ref(field: str, scope: Literal["data", "capabilities"] = "data") -> ReferenceValue:
    return ReferenceValue(kind="ref", scope=scope, field=field)


def notifications_document() -> FlowDocument:
    """Show current preferences and delegate all changes to the owning service.

    Status icons and translated labels are separate buttons in the same row. Both
    perform the same action; labels therefore always use the pinned DB catalog,
    including after an interrupted dialog changes language or theme.
    """
    outputs = {setting.value: setting.value for setting in NotificationSetting}
    buttons: list[list[Button]] = []
    for setting in NotificationSetting:
        name = setting.value
        value = LiteralValue(kind="literal", value=name)
        markers: list[Button] = [
            TransitionButton(
                kind="transition",
                id=f"{name}_{'on' if enabled else 'off'}",
                label=InlineText(kind="inline", translations={"en": "✅" if enabled else "❌"}),
                target="toggle",
                assignments={"selected": value},
                when=Compare(
                    kind="compare",
                    left=_ref(name),
                    operator="eq",
                    right=LiteralValue(kind="literal", value=enabled),
                ),
            )
            for enabled in (True, False)
        ]
        markers.append(
            TransitionButton(
                kind="transition",
                id=name,
                label=CatalogText(kind="catalog", key=f"notifications.{name}"),
                target="toggle",
                assignments={"selected": value},
            )
        )
        buttons.append(markers)
    buttons.insert(
        1,
        [
            TransitionButton(
                kind="transition", id="food", label=CatalogText(kind="catalog", key="menu.food"), target="food"
            )
        ],
    )
    buttons.append(
        [
            TransitionButton(
                kind="transition",
                id="eders",
                label=CatalogText(kind="catalog", key="notifications.eders"),
                target="eders",
                when=Compare(
                    kind="compare",
                    left=_ref("eders_enabled", "capabilities"),
                    operator="eq",
                    right=LiteralValue(kind="literal", value=True),
                ),
            )
        ]
    )
    buttons.append(
        [
            TransitionButton(
                kind="transition", id="back", label=CatalogText(kind="catalog", key="common.back"), target="completed"
            )
        ]
    )
    nodes: list[Node] = [
        ActionNode(
            kind="action",
            id="load",
            delegate="notifications.get_settings",
            results=outputs,
            outcomes={"success": "menu", "not_found": "not_found"},
        ),
        MenuNode(
            kind="menu",
            id="menu",
            text=[CatalogText(kind="catalog", key="notifications.title")],
            keyboard="inline",
            buttons=buttons,
        ),
        ActionNode(
            kind="action",
            id="toggle",
            delegate="notifications.toggle_setting",
            arguments={"setting": _ref("selected")},
            results=outputs,
            outcomes={"success": "menu", "not_found": "not_found"},
        ),
        CallNode(
            kind="call",
            id="food",
            flow="food_menu_notifications",
            outcomes={"completed": "load", "cancelled": "load"},
        ),
        EndNode(kind="end", id="eders", status="handed_off", feature="eders_notifications"),
        ReturnNode(kind="return", id="completed", outcome="completed"),
        ReturnNode(
            kind="return",
            id="not_found",
            outcome="cancelled",
            text=[CatalogText(kind="catalog", key="common.start_required")],
        ),
    ]
    return FlowDocument(
        schema_version=2,
        id="notifications_menu",
        entry="load",
        fields={
            **{name: DataField(type="boolean", nullable=True) for name in outputs},
            "selected": DataField(type="text"),
        },
        outcomes=["completed", "cancelled"],
        nodes=nodes,
    )
