from datetime import datetime

from aiogram.utils.i18n import gettext as _

from manashelper.services.eders_models import BISHKEK_TZ, ActivityKind, EdersActivity, EdersGrade
from manashelper.services.html_sanitization import escape_html

FEEDBACK_PAGE_SIZE = 350


def format_material_kind(kind: ActivityKind) -> str:
    return {
        ActivityKind.ASSIGNMENT: _("eders.kind_assignment"),
        ActivityKind.QUIZ: _("eders.kind_quiz"),
        ActivityKind.RESOURCE: _("eders.kind_resource"),
        ActivityKind.LINK: _("eders.kind_link"),
        ActivityKind.PAGE: _("eders.kind_page"),
        ActivityKind.BOOK: _("eders.kind_book"),
        ActivityKind.FOLDER: _("eders.kind_folder"),
        ActivityKind.LESSON: _("eders.kind_lesson"),
        ActivityKind.H5P: _("eders.kind_h5p"),
        ActivityKind.LABEL: _("eders.kind_label"),
    }.get(kind, _("eders.unknown"))


def format_feedback_page(grade: EdersGrade, page: int, count: int) -> str:
    feedback = grade.feedback or _("eders.unknown")
    return "\n\n".join(
        [
            _("eders.feedback_header"),
            _("eders.page").format(page=page + 1, count=count),
            f"<b>{_value(grade.course.name, 70)}</b>",
            _value(grade.name, 100),
            escape_html(feedback[page * FEEDBACK_PAGE_SIZE : (page + 1) * FEEDBACK_PAGE_SIZE]),
        ]
    )


def _value(text: str | None, limit: int) -> str:
    if text is None:
        return _("eders.unknown")
    return escape_html(text[:limit] + ("…" if len(text) > limit else ""))


def format_grade(grade: EdersGrade) -> str:
    return "\n".join(
        [
            f"<b>{_value(grade.course.name, 70)}</b>",
            f'<a href="{escape_html(grade.url)}">{_value(grade.name, 100)}</a>',
            _("eders.grade_value").format(value=_value(grade.grade, 40)),
            _("eders.grade_range").format(value=_value(grade.range, 40)),
            _("eders.grade_percentage").format(value=_value(grade.percentage, 30)),
            _("eders.grade_weight").format(value=_value(grade.weight, 30)),
            _("eders.grade_contribution").format(value=_value(grade.contribution, 30)),
            _("eders.grade_feedback").format(value=_value(grade.feedback, 200)),
        ]
    )


def format_catalog_page(
    item: EdersActivity | EdersGrade | None, *, grades: bool, page: int, count: int, updated: datetime
) -> str:
    header = _("eders.grades_header") if grades else _("eders.materials_header")
    lines = [header, _("eders.page").format(page=page + 1 if count else 0, count=count)]
    if isinstance(item, EdersGrade):
        lines.append(format_grade(item))
    elif isinstance(item, EdersActivity):
        lines.extend(
            [
                f"<b>{_value(item.course.name, 100)}</b>",
                _("eders.material_type").format(value=format_material_kind(item.kind)),
                _("eders.section").format(value=_value(item.section or None, 150)),
                f'<a href="{escape_html(item.url)}">{_value(item.name, 300)}</a>',
            ]
        )
    else:
        lines.append(_("eders.catalog_empty"))
    lines.extend(
        [
            _("eders.updated_at").format(value=updated.astimezone(BISHKEK_TZ).strftime("%d.%m.%Y %H:%M")),
            _("eders.grade_source_note") if grades else _("eders.materials_search_hint"),
        ]
    )
    return "\n\n".join(lines)
