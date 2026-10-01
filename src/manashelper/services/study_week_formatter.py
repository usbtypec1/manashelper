from datetime import timedelta

from aiogram.utils.i18n import gettext as _

from manashelper.services.eders_models import BISHKEK_TZ, ActivityKind
from manashelper.services.html_sanitization import escape_html
from manashelper.services.study_week import StudyWeek, week_end
from manashelper.services.timetable_formatter import weekday_full


def format_study_week(week: StudyWeek) -> list[str]:
    lines = [_("eders.week_header").format(start=week.start.strftime("%d.%m"), end=week_end(week).strftime("%d.%m"))]
    if not week.has_tracked_courses:
        lines.append(_("eders.week_no_schedule"))
    for offset in range(7):
        day = week.start + timedelta(days=offset)
        events: list[tuple[str, str]] = []
        for lesson in week.lessons:
            if lesson.weekday == day.isoweekday():
                events.append(
                    (
                        lesson.time_range.split("-", 1)[0].zfill(5),
                        f"{escape_html(lesson.time_range)} — {escape_html(lesson.content[:200])}",
                    )
                )
        deadline_count = 0
        for item in week.snapshot.activities:
            label = f'<a href="{escape_html(item.url)}">{escape_html(item.name[:200])}</a>'
            label = f"{escape_html(item.course.name[:120])}: {label}"
            for value, opening in ((item.opens, True), (item.closes, False)):
                if value.instant and not value.conflict and value.instant.astimezone(BISHKEK_TZ).date() == day:
                    time = value.instant.astimezone(BISHKEK_TZ).strftime("%H:%M")
                    kind = _("eders.week_opens") if opening else _("eders.week_due")
                    events.append((time, f"{time} — {kind}: {label}"))
                    if not opening:
                        deadline_count += 1
            if (
                item.kind in {ActivityKind.RESOURCE, ActivityKind.LINK}
                and item.first_seen
                and item.first_seen.astimezone(BISHKEK_TZ).date() == day
            ):
                events.append(("99:99", _("eders.week_material").format(value=label)))
        lines.extend(["", f"<b>{day.strftime('%d.%m')} — {weekday_full(day.isoweekday())}</b>"])
        if deadline_count > 1:
            lines.append(_("eders.week_many_deadlines").format(count=deadline_count))
        lines.extend(text for _, text in sorted(events))
        if not events:
            lines.append(_("eders.week_empty_day"))
    lines.extend(["", _("eders.filter_note")])
    # Split at complete lines so Telegram's limit never cuts an HTML entity or tag.
    chunks: list[str] = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 3500:
            chunks.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks
