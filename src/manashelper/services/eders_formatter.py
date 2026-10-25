from aiogram.utils.i18n import gettext as _

from manashelper.platform.telegram.html import escape_html
from manashelper.services.eders_models import (
    ActivityDate,
    ActivityKind,
    EdersActivity,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.services.eders_tracking import EdersEvent
from manashelper.services.time_utils import BISHKEK_TZ


def _date(value: ActivityDate, source_limit: int = 300) -> str:
    if value.conflict:
        return _("eders.date_conflict").format(value=escape_html((value.source_text or "")[:source_limit]))
    if value.instant is not None:
        return escape_html(value.instant.astimezone(BISHKEK_TZ).strftime("%d.%m.%Y %H:%M"))
    if value.source_text:
        return _("eders.date_unverified").format(value=escape_html(value.source_text[:source_limit]))
    return _("eders.unknown")


def _submission(value: SubmissionStatus) -> str:
    return {
        SubmissionStatus.UNKNOWN: _("eders.unknown"),
        SubmissionStatus.NOT_SUBMITTED: _("eders.not_submitted"),
        SubmissionStatus.DRAFT: _("eders.draft"),
        SubmissionStatus.SUBMITTED: _("eders.submitted"),
        SubmissionStatus.IN_PROGRESS: _("eders.in_progress"),
    }[value]


def _grading(value: GradingStatus) -> str:
    return {
        GradingStatus.UNKNOWN: _("eders.unknown"),
        GradingStatus.NOT_GRADED: _("eders.not_graded"),
        GradingStatus.GRADED: _("eders.graded"),
    }[value]


def format_activity_page(activities: list[EdersActivity], page: int) -> str:
    header = _("eders.page").format(page=page + 1 if activities else 0, count=len(activities))
    if not activities:
        return f"{header}\n\n{_('eders.empty')}\n\n{_('eders.filter_note')}"
    activity = activities[page]
    lines = [
        header,
        "",
        f"<b>{escape_html(activity.course.name[:200])}</b>",
        f'<a href="{escape_html(activity.url)}">{escape_html(activity.name[:300])}</a>',
    ]
    if activity.section:
        lines.append(escape_html(activity.section[:200]))
    if activity.kind in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
        lines.extend(
            [
                _("eders.opens").format(value=_date(activity.opens)),
                _("eders.closes").format(value=_date(activity.closes)),
                _("eders.submission").format(value=_submission(activity.submission)),
                _("eders.grading").format(value=_grading(activity.grading)),
            ]
        )
    elif activity.description:
        lines.append(escape_html(activity.description[:800]))
    if activity.title_date_mismatch:
        lines.append(_("eders.title_date_mismatch"))
    lines.extend(
        [
            "",
            _("eders.filter_note")
            if activity.kind in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}
            else _("eders.materials_help"),
        ]
    )
    return "\n".join(lines)


def format_eders_event(event: EdersEvent) -> str:
    headers = {
        "before_24": _("eders.reminder_day"),
        "before_2": _("eders.reminder_two_hours"),
        "opened": _("eders.opened_notification"),
        "changed": _("eders.changed_notification"),
        "material_new": _("eders.material_new"),
        "material_changed": _("eders.material_changed"),
    }
    item = event.activity
    lines = [
        headers[event.event_type],
        escape_html(item.course.name[:200]),
        f'<a href="{escape_html(item.url)}">{escape_html(item.name[:300])}</a>',
    ]
    if event.previous_deadline:
        lines.append(_("eders.previous_deadline").format(value=_date(ActivityDate(event.previous_deadline))))
    lines.append(_("eders.closes").format(value=_date(item.closes)))
    return "\n".join(lines)


def format_material_events(events: list[EdersEvent]) -> list[tuple[str, list[EdersEvent]]]:
    grouped: dict[int, list[EdersEvent]] = {}
    for event in events:
        grouped.setdefault(event.activity.course.id, []).append(event)
    messages = []
    for course_events in grouped.values():
        header = f"📚 {escape_html(course_events[0].activity.course.name[:120])}"
        text = header
        batch: list[EdersEvent] = []
        for event in course_events:
            item = event.activity
            label = _("eders.material_new") if event.event_type == "material_new" else _("eders.material_changed")
            block = f'\n\n{label}\n<a href="{escape_html(item.url)}">{escape_html(item.name[:180])}</a>'
            if item.section:
                block += f"\n{escape_html(item.section[:100])}"
            if item.closes.instant or item.closes.source_text:
                block += "\n" + _("eders.closes").format(value=_date(item.closes, source_limit=100))
            if len(text) + len(block) > 3500 and batch:
                messages.append((text, batch))
                text, batch = header, []
            text += block
            batch.append(event)
        if batch:
            messages.append((text, batch))
    return messages
