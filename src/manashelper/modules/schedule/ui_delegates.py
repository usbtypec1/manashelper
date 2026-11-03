"""Transactional Schedule adapters; durable documents own navigation and snapshots."""

from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from html.parser import HTMLParser
from typing import Literal, cast
from uuid import UUID

from manashelper.core.time import BISHKEK_TZ
from manashelper.localization.weekdays import weekday_abbr
from manashelper.modules.schedule.application.course import (
    CourseNotFoundError,
    CourseService,
    CourseSummary,
    UserNotFoundError,
)
from manashelper.modules.schedule.application.department import DepartmentService
from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.application.lesson_search import LessonSearchResult, LessonSearchService
from manashelper.modules.schedule.application.schedule import NoTrackedCoursesError, ScheduleService
from manashelper.modules.schedule.presentation.lesson_search_formatter import (
    format_lesson_search_page,
    total_page_count,
)
from manashelper.modules.schedule.presentation.timetable_formatter import format_day_schedule
from manashelper.platform.i18n.catalog import i18n
from ui_flows.application.delegates import DelegateBinding
from ui_flows.domain.contracts import Delegate, DelegateContext, DelegateDefinition, DelegateParameter, DelegateResult
from ui_flows.domain.schema import DataField, DataValue
from ui_flows.errors import FlowExecutionError

CATALOG_PAGE_SIZE = 16
SNAPSHOT_LIMIT = 1000

OPTION_FIELD = DataField(type="object", properties={"id": DataField(type="text"), "label": DataField(type="text")})
OPTIONS_FIELD = DataField(type="list", items=OPTION_FIELD, max_items=SNAPSHOT_LIMIT)
RESULT_FIELD = DataField(
    type="object",
    properties={
        "course_id": DataField(type="integer"),
        "course_number": DataField(type="integer"),
        "faculty_name": DataField(type="text"),
        "department_name": DataField(type="text"),
        "weekday": DataField(type="integer"),
        "content": DataField(type="text"),
        "time_ranges": DataField(type="list", items=DataField(type="text"), max_items=100),
    },
)
RESULTS_FIELD = DataField(type="list", items=RESULT_FIELD, max_items=SNAPSHOT_LIMIT)
CHUNKS_FIELD = DataField(type="list", items=DataField(type="text"), max_items=20)
DAY_FIELD = DataField(type="object", properties={"id": DataField(type="integer"), "label": DataField(type="text")})
PAGE_OUTPUTS = {
    "visible": DataField(type="list", items=OPTION_FIELD, max_items=CATALOG_PAGE_SIZE),
    "page": DataField(type="integer"),
    "previous": DataField(type="integer"),
    "following": DataField(type="integer"),
    "has_previous": DataField(type="boolean"),
    "has_following": DataField(type="boolean"),
}


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain(text: str) -> str:
    # Existing presenters escape source values before HTML formatting. Decode only after
    # parsing, so a source string such as "<b>" remains visible source text, never markup.
    parser = _PlainText()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def _chunks(text: str) -> list[DataValue]:
    # Raw text is escaped once by the renderer. 1800 UTF-16 units also leave room for
    # expanding HTML entities without ever splitting a surrogate pair or dropping data.
    chunks: list[DataValue] = []
    current = ""
    units = 0
    for line in text.splitlines(keepends=True):
        line_units = len(line.encode("utf-16-le")) // 2
        if current and units + line_units > 1800:
            chunks.append(current)
            current, units = "", 0
        for char in line:
            width = len(char.encode("utf-16-le")) // 2
            if units + width > 1800:
                chunks.append(current)
                current, units = "", 0
            current += char
            units += width
    if current:
        chunks.append(current)
    if len(chunks) > 20:
        raise FlowExecutionError("Schedule output exceeds the supported delivery size")
    return chunks


def _label(text: str) -> str:
    result, units = "", 0
    for char in text:
        width = len(char.encode("utf-16-le")) // 2
        if units + width > 60:
            return result + "…"
        result += char
        units += width
    return result or "—"


def _check_context(context: DelegateContext) -> None:
    if context.user_id <= 0 or context.chat_id != context.user_id:
        raise FlowExecutionError("Schedule dialogs require the authenticated private actor")


def _identifier(value: DataValue) -> UUID:
    if not isinstance(value, str):
        raise FlowExecutionError("A catalog identifier is required")
    try:
        return UUID(value)
    except ValueError:
        raise FlowExecutionError("A catalog identifier is invalid") from None


def _bounded(items: list[DataValue]) -> list[DataValue]:
    if len(items) > SNAPSHOT_LIMIT:
        raise FlowExecutionError("Schedule collection exceeds its declared snapshot bound")
    return items


def _options(courses: list[CourseSummary]) -> list[DataValue]:
    return _bounded(
        [
            {
                "id": str(course.id),
                "label": ("✅ " if course.is_tracked else "")
                + i18n.gettext("schedule.course_year").format(number=course.number),
            }
            for course in courses
        ]
    )


class ScheduleUiDelegates:
    def __init__(
        self,
        faculties: FacultyService,
        departments: DepartmentService,
        courses: CourseService,
        schedule: ScheduleService,
        search: LessonSearchService,
    ) -> None:
        self._faculties = faculties
        self._departments = departments
        self._courses = courses
        self._schedule = schedule
        self._search = search

    async def faculties(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        items: list[DataValue] = [
            {"id": str(item.id), "label": _label(item.name)} for item in await self._faculties.get_all_faculties()
        ]
        return DelegateResult("success", {"options": _bounded(items)})

    async def departments(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        items: list[DataValue] = [
            {"id": str(item.id), "label": _label(item.name)}
            for item in await self._departments.get_departments_by_faculty(_identifier(arguments["faculty_id"]))
        ]
        return DelegateResult("success", {"options": _bounded(items)})

    async def courses(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        courses = await self._courses.get_courses_by_department(
            _identifier(arguments["department_id"]), context.user_id
        )
        return DelegateResult("success", {"options": _options(courses)})

    async def toggle_course(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        candidate = arguments["course_id"]
        if not isinstance(candidate, str) or not candidate.isascii() or not candidate.isdecimal():
            raise FlowExecutionError("A selected course identifier is required")
        try:
            courses = await self._courses.toggle_tracked_course(int(candidate), context.user_id)
        except CourseNotFoundError:
            return DelegateResult("missing", {"options": []})
        except UserNotFoundError:
            return DelegateResult("unknown_user", {"options": []})
        return DelegateResult("success", {"options": _options(courses)})

    async def catalog_page(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        items = cast(list[DataValue], arguments["options"])
        last = max((len(items) - 1) // CATALOG_PAGE_SIZE, 0)
        page = min(max(cast(int, arguments["page"]), 0), last)
        return DelegateResult(
            "success",
            {
                "visible": items[page * CATALOG_PAGE_SIZE : (page + 1) * CATALOG_PAGE_SIZE],
                "page": page,
                "previous": max(page - 1, 0),
                "following": min(page + 1, last),
                "has_previous": page > 0,
                "has_following": page < last,
            },
        )

    async def day(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        now = datetime.now(BISHKEK_TZ)
        selected = cast(int, arguments["weekday"])
        if selected == 0:
            selected = now.isoweekday() if now.isoweekday() <= 5 else 1
        if not 1 <= selected <= 5:
            raise FlowExecutionError("A workday is required")
        empty: dict[str, DataValue] = {"chunks": [], "days": [], "weekday": selected}
        try:
            lessons = await self._schedule.get_user_schedule(context.user_id)
        except UserNotFoundError:
            return DelegateResult("unknown_user", empty)
        except NoTrackedCoursesError:
            return DelegateResult("no_courses", empty)
        if not lessons:
            return DelegateResult("not_loaded", empty)
        days: list[DataValue] = [{"id": day, "label": weekday_abbr(day)} for day in range(1, 6) if day != selected]
        return DelegateResult(
            "success",
            {"chunks": _chunks(_plain(format_day_schedule(selected, lessons, now))), "days": days, "weekday": selected},
        )

    async def search(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        query = cast(str, arguments["query"]).strip()
        if len(query) < 2:
            return DelegateResult("too_short", {"snapshot": []})
        results = await self._search.search(query)
        if not results:
            return DelegateResult("empty", {"snapshot": []})
        snapshot: list[DataValue] = [cast(dict[str, DataValue], asdict(item)) for item in results]
        return DelegateResult("success", {"snapshot": _bounded(snapshot)})

    async def search_page(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        _check_context(context)
        snapshot = cast(list[dict[str, DataValue]], arguments["snapshot"])
        if not snapshot:
            return DelegateResult(
                "expired",
                {"chunks": [], "page": 0, "previous": 0, "following": 0, "has_previous": False, "has_following": False},
            )
        results = [
            LessonSearchResult(
                course_id=cast(int, row["course_id"]),
                course_number=cast(int, row["course_number"]),
                faculty_name=cast(str, row["faculty_name"]),
                department_name=cast(str, row["department_name"]),
                weekday=cast(int, row["weekday"]),
                content=cast(str, row["content"]),
                time_ranges=cast(list[str], row["time_ranges"]),
            )
            for row in snapshot
        ]
        last = total_page_count(results) - 1
        page = min(max(cast(int, arguments["page"]), 0), last)
        return DelegateResult(
            "success",
            {
                "chunks": _chunks(_plain(format_lesson_search_page(results, page))),
                "page": page,
                "previous": max(page - 1, 0),
                "following": min(page + 1, last),
                "has_previous": page > 0,
                "has_following": page < last,
            },
        )

    def bindings(self) -> list[DelegateBinding]:
        def binding(
            name: str,
            handler: Delegate,
            *,
            inputs: dict[str, DelegateParameter] | None = None,
            outputs: dict[str, DataField] | None = None,
            outcomes: list[str] | None = None,
            effect: Literal["read", "database_write"] = "read",
        ) -> DelegateBinding:
            return DelegateBinding(
                DelegateDefinition(
                    id="schedule." + name,
                    effect=effect,
                    inputs=inputs or {},
                    outputs=outputs or {},
                    outcomes=outcomes or ["success"],
                ),
                handler,
            )

        return [
            binding("faculties", self.faculties, outputs={"options": OPTIONS_FIELD}),
            binding(
                "departments",
                self.departments,
                inputs={"faculty_id": DelegateParameter(type="text")},
                outputs={"options": OPTIONS_FIELD},
            ),
            binding(
                "courses",
                self.courses,
                inputs={"department_id": DelegateParameter(type="text")},
                outputs={"options": OPTIONS_FIELD},
            ),
            binding(
                "toggle_course",
                self.toggle_course,
                inputs={"course_id": DelegateParameter(type="text")},
                outputs={"options": OPTIONS_FIELD},
                outcomes=["success", "missing", "unknown_user"],
                effect="database_write",
            ),
            binding(
                "catalog_page",
                self.catalog_page,
                inputs={
                    "options": DelegateParameter(**OPTIONS_FIELD.model_dump()),
                    "page": DelegateParameter(type="integer"),
                },
                outputs=PAGE_OUTPUTS,
            ),
            binding(
                "day",
                self.day,
                inputs={"weekday": DelegateParameter(type="integer")},
                outputs={
                    "chunks": CHUNKS_FIELD,
                    "days": DataField(type="list", items=DAY_FIELD, max_items=5),
                    "weekday": DataField(type="integer"),
                },
                outcomes=["success", "unknown_user", "no_courses", "not_loaded"],
            ),
            binding(
                "search",
                self.search,
                inputs={"query": DelegateParameter(type="text")},
                outputs={"snapshot": RESULTS_FIELD},
                outcomes=["success", "too_short", "empty"],
            ),
            binding(
                "search_page",
                self.search_page,
                inputs={
                    "snapshot": DelegateParameter(**RESULTS_FIELD.model_dump()),
                    "page": DelegateParameter(type="integer"),
                },
                outputs={
                    "chunks": CHUNKS_FIELD,
                    **{key: value for key, value in PAGE_OUTPUTS.items() if key != "visible"},
                },
                outcomes=["success", "expired"],
            ),
        ]
