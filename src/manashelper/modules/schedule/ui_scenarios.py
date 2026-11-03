"""Initial Schedule scenario documents; operator-authored DB versions stay authoritative."""

from typing import Literal

from manashelper.modules.schedule.ui_delegates import (
    CHUNKS_FIELD,
    DAY_FIELD,
    OPTIONS_FIELD,
    PAGE_OUTPUTS,
    RESULTS_FIELD,
)
from ui_flows.domain.schema import (
    ActionNode,
    Button,
    CallNode,
    CatalogText,
    Compare,
    DataField,
    FlowDocument,
    InlineText,
    InputNode,
    LiteralValue,
    MenuNode,
    Node,
    ReferenceValue,
    RepeatedButtons,
    ReturnNode,
    TransitionButton,
    Value,
)


def _ref(field: str, scope: Literal["data", "item"] = "data") -> ReferenceValue:
    return ReferenceValue(kind="ref", scope=scope, field=field)


def _literal(value: str | int | bool) -> LiteralValue:
    return LiteralValue(kind="literal", value=value)


def _catalog(key: str) -> CatalogText:
    return CatalogText(kind="catalog", key=key)


def _label(field: str, scope: Literal["data", "item"] = "data") -> InlineText:
    return InlineText(kind="inline", translations={"en": "{value}"}, parameters={"value": _ref(field, scope)})


def _button(
    identifier: str,
    key: str,
    target: str,
    *,
    assignments: dict[str, Value] | None = None,
) -> TransitionButton:
    return TransitionButton(
        kind="transition", id=identifier, label=_catalog(key), target=target, assignments=assignments or {}
    )


def _return(outcome: Literal["completed", "cancelled"]) -> ReturnNode:
    return ReturnNode(
        kind="return",
        id=outcome,
        outcome=outcome,
        text=[_catalog("common.cancelled")] if outcome == "cancelled" else [],
    )


def _back(target: str = "cancelled") -> list[Button]:
    return [_button("back", "common.back", target)]


def _pager(target: str) -> list[Button]:
    return [
        TransitionButton(
            kind="transition",
            id=name,
            label=InlineText(kind="inline", translations={"en": arrow}),
            target=target,
            assignments={"page": _ref(name)},
            when=Compare(kind="compare", left=_ref("has_" + name), operator="eq", right=_literal(True)),
        )
        for name, arrow in (("previous", "◀️"), ("following", "▶️"))
    ]


def _repeated(source: str, target: str, selected: str) -> RepeatedButtons:
    return RepeatedButtons(
        source=_ref(source),
        buttons=[
            TransitionButton(
                kind="transition",
                id="choose",
                label=_label("label", "item"),
                target=target,
                assignments={selected: _ref("id", "item")},
            )
        ],
    )


def _action(
    identifier: str,
    delegate: str,
    target: str,
    *,
    arguments: dict[str, Value] | None = None,
    results: dict[str, str] | None = None,
    outcomes: dict[str, str] | None = None,
) -> ActionNode:
    return ActionNode(
        kind="action",
        id=identifier,
        delegate="schedule." + delegate,
        arguments=arguments or {},
        results=results or {},
        outcomes=outcomes or {"success": target},
    )


def _page_action(target: str = "choose") -> ActionNode:
    return _action(
        "page",
        "catalog_page",
        target,
        arguments={"options": _ref("options"), "page": _ref("page")},
        results={field: field for field in PAGE_OUTPUTS},
    )


def _page_fields() -> dict[str, DataField]:
    return {"options": OPTIONS_FIELD, **PAGE_OUTPUTS}


def _catalog_scenario(*, department: bool) -> FlowDocument:
    selected = "department_id" if department else "faculty_id"
    return FlowDocument(
        schema_version=2,
        id="select_department" if department else "select_faculty",
        entry="load",
        inputs={"faculty_id": DataField(type="text")} if department else {},
        outputs={selected: DataField(type="text")},
        fields={
            **_page_fields(),
            selected: DataField(type="text"),
            **({"faculty_id": DataField(type="text")} if department else {}),
        },
        outcomes=["completed", "cancelled"],
        initial_data={"page": 0, selected: ""},
        nodes=[
            _action(
                "load",
                "departments" if department else "faculties",
                "page",
                arguments={"faculty_id": _ref("faculty_id")} if department else {},
                results={"options": "options"},
            ),
            _page_action(),
            MenuNode(
                kind="menu",
                id="choose",
                keyboard="inline",
                text=[_catalog("schedule.departments" if department else "schedule.faculties")],
                buttons=[_pager("page"), _back()],
                repeated=[_repeated("visible", "completed", selected)],
            ),
            ReturnNode(kind="return", id="completed", outcome="completed", values={selected: _ref(selected)}),
            _return("cancelled").model_copy(update={"values": {selected: _ref(selected)}}),
        ],
    )


def _course_tracking() -> FlowDocument:
    return FlowDocument(
        schema_version=2,
        id="course_tracking",
        entry="faculty",
        fields={
            **_page_fields(),
            "faculty_id": DataField(type="text"),
            "department_id": DataField(type="text"),
            "course_id": DataField(type="text"),
        },
        initial_data={"page": 0},
        outcomes=["completed", "cancelled"],
        nodes=[
            CallNode(
                kind="call",
                id="faculty",
                flow="select_faculty",
                results={"faculty_id": "faculty_id"},
                outcomes={"completed": "department", "cancelled": "cancelled"},
            ),
            CallNode(
                kind="call",
                id="department",
                flow="select_department",
                arguments={"faculty_id": _ref("faculty_id")},
                results={"department_id": "department_id"},
                outcomes={"completed": "load", "cancelled": "faculty"},
            ),
            _action(
                "load",
                "courses",
                "page",
                arguments={"department_id": _ref("department_id")},
                results={"options": "options"},
            ),
            _page_action(),
            MenuNode(
                kind="menu",
                id="choose",
                keyboard="inline",
                text=[_catalog("schedule.courses")],
                buttons=[_pager("page"), _back("department"), [_button("done", "common.done", "completed")]],
                repeated=[_repeated("visible", "toggle", "course_id")],
            ),
            _action(
                "toggle",
                "toggle_course",
                "page",
                arguments={"course_id": _ref("course_id")},
                results={"options": "options"},
                outcomes={"success": "page", "missing": "missing", "unknown_user": "unknown_user"},
            ),
            MenuNode(
                kind="menu",
                id="missing",
                keyboard="inline",
                text=[_catalog("schedule.course_not_found")],
                buttons=[_back("load")],
            ),
            MenuNode(
                kind="menu",
                id="unknown_user",
                keyboard="inline",
                text=[_catalog("common.start_required")],
                buttons=[_back()],
            ),
            _return("completed"),
            _return("cancelled"),
        ],
    )


def _my_schedule() -> FlowDocument:
    nodes: list[Node] = [
        _action(
            "load",
            "day",
            "day",
            arguments={"weekday": _ref("weekday")},
            results={"chunks": "chunks", "days": "days", "weekday": "weekday"},
            outcomes={
                "success": "day",
                "unknown_user": "unknown_user",
                "no_courses": "no_courses",
                "not_loaded": "not_loaded",
            },
        ),
        MenuNode(
            kind="menu",
            id="day",
            keyboard="inline",
            text=[_catalog("schedule.my_schedule")],
            message_source=_ref("chunks"),
            buttons=[_back(), [_button("done", "common.done", "completed")]],
            repeated=[_repeated("days", "load", "weekday")],
        ),
        MenuNode(
            kind="menu",
            id="no_courses",
            keyboard="inline",
            text=[_catalog("schedule.no_tracked_courses")],
            buttons=[[_button("track", "schedule.choose_courses", "tracking")], _back()],
        ),
        CallNode(
            kind="call",
            id="tracking",
            flow="course_tracking",
            outcomes={"completed": "load", "cancelled": "no_courses"},
        ),
        _return("cancelled"),
        _return("completed"),
    ]
    for identifier, key in (("unknown_user", "common.start_required"), ("not_loaded", "schedule.not_loaded")):
        nodes.append(MenuNode(kind="menu", id=identifier, keyboard="inline", text=[_catalog(key)], buttons=[_back()]))
    return FlowDocument(
        schema_version=2,
        id="my_schedule",
        entry="load",
        fields={
            "weekday": DataField(type="integer"),
            "chunks": CHUNKS_FIELD,
            "days": DataField(type="list", items=DAY_FIELD, max_items=5),
        },
        initial_data={"weekday": 0},
        outcomes=["completed", "cancelled"],
        nodes=nodes,
    )


def _lesson_search() -> FlowDocument:
    nodes: list[Node] = [
        InputNode(
            kind="input",
            id="query",
            field="query",
            input_type="text",
            min_length=1,
            max_length=4000,
            next="search",
            text=[_catalog("schedule.search_prompt")],
            error=_catalog("schedule.query_too_short"),
            buttons=[_back()],
        ),
        _action(
            "search",
            "search",
            "first_page",
            arguments={"query": _ref("query")},
            results={"snapshot": "snapshot"},
            outcomes={"success": "first_page", "too_short": "too_short", "empty": "empty"},
        ),
        _action(
            "first_page",
            "search_page",
            "results",
            arguments={"snapshot": _ref("snapshot"), "page": _literal(0)},
            results={field: field for field in PAGE_OUTPUTS if field != "visible"} | {"chunks": "chunks"},
            outcomes={"success": "results", "expired": "expired"},
        ),
        _action(
            "page",
            "search_page",
            "results",
            arguments={"snapshot": _ref("snapshot"), "page": _ref("page")},
            results={field: field for field in PAGE_OUTPUTS if field != "visible"} | {"chunks": "chunks"},
            outcomes={"success": "results", "expired": "expired"},
        ),
        MenuNode(
            kind="menu",
            id="results",
            keyboard="inline",
            text=[_catalog("schedule.search_subject")],
            message_source=_ref("chunks"),
            buttons=[
                _pager("page"),
                [_button("search_again", "schedule.search_subject", "query")],
                _back(),
                [_button("done", "common.done", "completed")],
            ],
        ),
        _return("completed"),
        _return("cancelled"),
    ]
    for identifier, key in (
        ("too_short", "schedule.query_too_short"),
        ("empty", "schedule.no_results"),
        ("expired", "schedule.search_expired"),
    ):
        nodes.append(
            MenuNode(
                kind="menu",
                id=identifier,
                keyboard="inline",
                text=[_catalog(key)],
                buttons=[[_button("search_again", "schedule.search_subject", "query")], _back()],
            )
        )
    return FlowDocument(
        schema_version=2,
        id="lesson_search",
        entry="query",
        fields={
            "query": DataField(type="text"),
            "snapshot": RESULTS_FIELD,
            "chunks": CHUNKS_FIELD,
            **{field: shape for field, shape in PAGE_OUTPUTS.items() if field != "visible"},
        },
        outcomes=["completed", "cancelled"],
        nodes=nodes,
    )


def _schedule_menu() -> FlowDocument:
    nodes: list[Node] = [
        MenuNode(
            kind="menu",
            id="menu",
            keyboard="inline",
            text=[_catalog("menu.schedule")],
            buttons=[
                [_button("my_schedule", "schedule.my_schedule", "schedule")],
                [_button("search", "schedule.search_subject", "search")],
                _back(),
                [_button("done", "common.done", "completed")],
            ],
        ),
        CallNode(kind="call", id="schedule", flow="my_schedule", outcomes={"completed": "menu", "cancelled": "menu"}),
        CallNode(kind="call", id="search", flow="lesson_search", outcomes={"completed": "menu", "cancelled": "menu"}),
        _return("cancelled"),
        _return("completed"),
    ]
    return FlowDocument(
        schema_version=2, id="schedule_menu", entry="menu", outcomes=["completed", "cancelled"], nodes=nodes
    )


def schedule_scenarios() -> list[FlowDocument]:
    # Dependencies precede their callers for the bootstrap's publish pass.
    return [
        _catalog_scenario(department=False),
        _catalog_scenario(department=True),
        _course_tracking(),
        _my_schedule(),
        _lesson_search(),
        _schedule_menu(),
    ]
