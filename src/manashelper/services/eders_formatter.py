from aiogram.utils.i18n import gettext as _

from manashelper.services.eders_models import BISHKEK_TZ, ActivityDate, EdersActivity, GradingStatus, SubmissionStatus
from manashelper.services.eders_tracking import EdersEvent
from manashelper.services.html_sanitization import escape_html


def _date(value: ActivityDate) -> str:
    if value.conflict:
        return _("eders.date_conflict").format(value=escape_html((value.source_text or "")[:300]))
    if value.instant is not None:
        return escape_html(value.instant.astimezone(BISHKEK_TZ).strftime("%d.%m.%Y %H:%M"))
    if value.source_text:
        return _("eders.date_unverified").format(value=escape_html(value.source_text[:300]))
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
        _("eders.opens").format(value=_date(activity.opens)),
        _("eders.closes").format(value=_date(activity.closes)),
        _("eders.submission").format(value=_submission(activity.submission)),
        _("eders.grading").format(value=_grading(activity.grading)),
    ]
    if activity.title_date_mismatch:
        lines.append(_("eders.title_date_mismatch"))
    lines.extend(["", _("eders.filter_note")])
    return "\n".join(lines)


def format_eders_event(event: EdersEvent) -> str:
    headers = {
        "before_24": _("eders.reminder_day"),
        "before_2": _("eders.reminder_two_hours"),
        "opened": _("eders.opened_notification"),
        "changed": _("eders.changed_notification"),
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
