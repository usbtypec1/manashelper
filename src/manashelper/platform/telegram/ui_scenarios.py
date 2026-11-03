"""Initial platform navigation scenarios; authored database versions stay authoritative."""

from ui_flows.domain.schema import (
    Button,
    CallNode,
    CatalogText,
    Compare,
    EndNode,
    FlowDocument,
    MenuNode,
    Node,
    Position,
    ReferenceValue,
    ReturnNode,
    TransitionButton,
)


def settings_document() -> FlowDocument:
    leaves = {
        "notifications": "settings.notifications",
        "course_tracking": "settings.my_lessons",
        "obis_credentials": "settings.obis_credentials",
        "phone_numbers": "settings.phone_numbers",
        "feedback": "settings.feedback",
    }
    entries = [
        *((feature, key) for feature, key in leaves.items() if feature != "feedback"),
        ("language", "settings.language"),
        ("theme", "settings.theme"),
        ("feedback", leaves["feedback"]),
        ("completed", "common.back_to_menu"),
    ]
    buttons: list[list[Button]] = [
        [
            TransitionButton(
                kind="transition",
                id="back" if destination == "completed" else destination,
                label=CatalogText(kind="catalog", key=key),
                target=destination,
                when=Compare(
                    kind="compare",
                    left=ReferenceValue(kind="ref", scope="user", field="id"),
                    operator="eq",
                    right=ReferenceValue(kind="ref", scope="capabilities", field="admin_id"),
                )
                if destination == "feedback"
                else None,
            )
        ]
        for destination, key in entries
    ]
    nodes: list[Node] = [
        MenuNode(
            kind="menu",
            id="menu",
            text=[CatalogText(kind="catalog", key="settings.title")],
            keyboard="inline",
            buttons=buttons,
        ),
        *[
            CallNode(
                kind="call",
                id=node_id,
                flow=flow_id,
                outcomes={"completed": "menu", "cancelled": "menu"},
            )
            for node_id, flow_id in (("language", "select_locale"), ("theme", "select_theme"))
        ],
        ReturnNode(kind="return", id="completed", outcome="completed"),
        *[EndNode(kind="end", id=feature, status="handed_off", feature=feature) for feature in leaves],
    ]
    return FlowDocument(
        schema_version=2,
        id="settings",
        entry="menu",
        outcomes=["completed", "cancelled"],
        nodes=nodes,
        layout={
            node.id: Position(x=float(80 + (index % 3) * 360), y=float(80 + (index // 3) * 260))
            for index, node in enumerate(nodes)
        },
    )
