from aiogram.utils.i18n import gettext as _

from manashelper.services.eders_catalog_formatter import format_grade
from manashelper.services.eders_models import (
    BISHKEK_TZ,
    ActivityDate,
    ActivityKind,
    EdersActivity,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.services.eders_tracking import EdersEvent
from manashelper.services.html_sanitization import escape_html


def _date(value: ActivityDate) -> str:
    if value.conflict:
        return _("eders.date_conflict").format(value=escape_html((value.source_text or "")[:70]))
    if value.instant is not None:
        return escape_html(value.instant.astimezone(BISHKEK_TZ).strftime("%d.%m.%Y %H:%M"))
    if value.source_text:
        return _("eders.date_unverified").format(value=escape_html(value.source_text[:70]))
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
        f"<b>{escape_html(activity.course.name[:70])}</b>",
        f'<a href="{escape_html(activity.url)}">{escape_html(activity.name[:100])}</a>',
        _("eders.opens").format(value=_date(activity.opens)),
        _("eders.closes").format(value=_date(activity.closes)),
        _("eders.submission").format(value=_submission(activity.submission)),
        _("eders.grading").format(value=_grading(activity.grading)),
    ]
    if activity.section:
        lines.append(_("eders.section").format(value=escape_html(activity.section[:50])))
    if activity.kind == ActivityKind.QUIZ:
        if activity.attempts:
            lines.append(_("eders.attempt_count").format(count=len(activity.attempts)))
        for attempt in activity.attempts[-3:]:
            lines.append(
                _("eders.attempt").format(
                    number=escape_html((attempt.number or "?")[:6]),
                    status=_submission(attempt.submission),
                    grade=escape_html((attempt.grade or _("eders.unknown"))[:20]),
                )
            )
        if activity.quiz_result:
            lines.append(_("eders.quiz_result").format(value=escape_html(activity.quiz_result[:50])))
    if activity.title_date_mismatch:
        lines.append(_("eders.title_date_mismatch"))
    lines.extend(["", _("eders.filter_note")])
    return "\n".join(lines)


def format_eders_event(event: EdersEvent) -> str:
    if event.grade is not None:
        lines = [_("eders.grade_notification"), format_grade(event.grade)]
        if event.previous_grade is not None:
            lines.append(
                _("eders.previous_grade").format(
                    value=escape_html((event.previous_grade.grade or _("eders.unknown"))[:40])
                )
            )
            lines.append(
                _("eders.previous_feedback").format(
                    value=escape_html((event.previous_grade.feedback or _("eders.unknown"))[:100])
                )
            )
        return "\n".join(lines)
    headers = {
        "before_24": _("eders.reminder_day"),
        "before_2": _("eders.reminder_two_hours"),
        "opened": _("eders.opened_notification"),
        "changed": _("eders.changed_notification"),
        "material_new": _("eders.material_notification"),
        "material_changed": _("eders.material_changed_notification"),
    }
    item = event.activity
    lines = [
        headers[event.event_type],
        escape_html(item.course.name[:200]),
        f'<a href="{escape_html(item.url)}">{escape_html(item.name[:300])}</a>',
    ]
    if event.previous_deadline:
        lines.append(_("eders.previous_deadline").format(value=_date(ActivityDate(event.previous_deadline))))
    if event.event_type.startswith("material_"):
        lines.append(_("eders.section").format(value=escape_html(item.section[:100]) or _("eders.unknown")))
    else:
        lines.append(_("eders.closes").format(value=_date(item.closes)))
    return "\n".join(lines)
