import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from bs4.element import Tag

from manashelper.core.time import BISHKEK_TZ
from manashelper.modules.eders.application.models import (
    ActivityDate,
    ActivityKind,
    EdersActivity,
    EdersCourse,
    GradingStatus,
    SubmissionStatus,
)
from manashelper.modules.eders.errors import EdersParseError, EdersUnsafeUrlError
from manashelper.modules.eders.infrastructure.urls import EDERS_BASE_URL, eders_id, safe_eders_url


def parse_enrolled_courses(payload: object) -> tuple[list[EdersCourse], int | None]:
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise EdersParseError("Invalid enrolled courses response")
    result = payload[0]
    if result.get("error"):
        raise EdersParseError("Eders rejected the enrolled courses request")
    data = result.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("courses"), list):
        raise EdersParseError("Missing enrolled courses")
    courses = {}
    for row in data["courses"]:
        if not isinstance(row, dict):
            raise EdersParseError("Invalid enrolled course")
        identifier, name = row.get("id"), row.get("fullname")
        if type(identifier) is not int or identifier <= 0 or not isinstance(name, str) or not name.strip():
            raise EdersParseError("Invalid enrolled course fields")
        courses[identifier] = EdersCourse(identifier, name.strip())
    next_offset = data.get("nextoffset")
    if next_offset is not None and type(next_offset) is not int:
        raise EdersParseError("Invalid course pagination")
    return list(courses.values()), next_offset


def _page(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one("input[name=logintoken], input[name='LoginForm[username]']"):
        raise EdersParseError("Authentication page instead of eders content")
    if soup.select_one("#region-main") is None:
        raise EdersParseError("Missing eders content region")
    if soup.select_one("#region-main .errorbox, #region-main .alert-danger"):
        raise EdersParseError("Eders error page")
    return soup


def parse_courses(html: str) -> list[EdersCourse]:
    soup = _page(html)
    table = soup.select_one("#region-main table#overview-grade")
    if table is None:
        # Moodle renders a notification for an account with no grade-report courses.
        empty = soup.select_one("#region-main .alert-info")
        if empty and empty.get_text(" ", strip=True) == "No courses":
            return []
        raise EdersParseError("Missing eders course overview table")
    courses: dict[int, EdersCourse] = {}
    for link in table.select("a[href]"):
        href = link.get("href")
        if not isinstance(href, str):
            continue
        parts = urlsplit(urljoin(EDERS_BASE_URL, href))
        params = parse_qs(parts.query, keep_blank_values=True)
        if parts.scheme != "https" or parts.netloc != "eders.manas.edu.kg" or parts.fragment:
            continue
        if parts.path not in {"/course/user.php", "/course/view.php", "/grade/report/user/index.php"}:
            continue
        if set(params) - {"id", "user", "userid", "mode", "group"} or params.get("mode", ["grade"]) != ["grade"]:
            continue
        ids = params.get("id", [])
        if len(ids) != 1 or not ids[0].isascii() or not ids[0].isdecimal() or int(ids[0]) <= 0:
            continue
        name = link.get_text(" ", strip=True)
        if name:
            identifier = int(ids[0])
            courses[identifier] = EdersCourse(identifier, name)
    if not courses and table.select("tbody tr"):
        raise EdersParseError("Unrecognized eders course overview rows")
    return list(courses.values())


def parse_account_timezone(html: str) -> ZoneInfo | None:
    return _account_timezone(_page(html))


def _account_timezone(soup: BeautifulSoup) -> ZoneInfo | None:
    # Actual Eders pages expose the effective timezone in Moodle's configuration.
    for script in soup.select("script"):
        match = re.search(r'"usertimezone"\s*:\s*("(?:[^"\\]|\\.)*")', script.get_text())
        if match:
            try:
                return ZoneInfo(json.loads(match[1]))
            except (ZoneInfoNotFoundError, ValueError, TypeError):
                pass
    for item in soup.select(".profile_tree dl"):
        label, value = item.select_one("dt"), item.select_one("dd")
        if label and value and label.get_text(" ", strip=True).casefold() == "timezone":
            try:
                return ZoneInfo(value.get_text(" ", strip=True))
            except (ZoneInfoNotFoundError, ValueError):
                return None
    return None


def _text_datetime(text: str, timezone: ZoneInfo | None) -> datetime | None:
    if timezone is None:
        return None
    normalized = " ".join(text.split())
    match = re.search(r"\b(\d{1,2}) ([^\W\d_]+) (20\d{2}),? (\d{1,2}):(\d{2})(?:\s*([AP]M))?\b", normalized)
    if match is None:
        return None
    day, month, year, hour, minute, am_pm = match.groups()
    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    turkish = [
        "ocak",
        "şubat",
        "mart",
        "nisan",
        "mayıs",
        "haziran",
        "temmuz",
        "ağustos",
        "eylül",
        "ekim",
        "kasım",
        "aralık",
    ]
    try:
        hours = int(hour)
        if am_pm:
            if not 1 <= hours <= 12:
                return None
            hours = hours % 12 + (12 if am_pm == "PM" else 0)
        month_names = months if month.casefold() in months else turkish
        value = datetime(
            int(year), month_names.index(month.casefold()) + 1, int(day), hours, int(minute), tzinfo=timezone
        )
        # Reject ambiguous and nonexistent local times across daylight-saving changes.
        if value.utcoffset() != value.replace(fold=1).utcoffset():
            return None
        if value.astimezone(UTC).astimezone(timezone) != value:
            return None
        return value.astimezone(BISHKEK_TZ)
    except ValueError:
        return None


def _parse_date(node: Tag, timezone: ZoneInfo | None) -> ActivityDate:
    text = node.get_text(" ", strip=True)
    label = node.select_one("strong")
    if label:
        text = text.removeprefix(label.get_text(" ", strip=True)).strip()
    time = node.select_one("time[datetime]")
    value = time.get("datetime") if time else None
    instant = None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                instant = parsed.astimezone(BISHKEK_TZ)
        except ValueError:
            pass
    if instant is None:
        instant = _text_datetime(text, timezone)
    return ActivityDate(instant=instant, source_text=text or None)


def _merge_date(first: ActivityDate, second: ActivityDate) -> ActivityDate:
    if not first.source_text and first.instant is None:
        return second
    if not second.source_text and second.instant is None:
        return first
    if first.conflict or second.conflict:
        return ActivityDate(source_text=second.source_text or first.source_text, conflict=True)
    if first.instant is not None and second.instant is not None:
        conflict = first.instant != second.instant
    else:
        conflict = first.source_text != second.source_text
    if conflict:
        texts = list(dict.fromkeys(t for t in (first.source_text, second.source_text) if t))
        return ActivityDate(source_text=" / ".join(texts) or None, conflict=True)
    return second


def _dates(node: Tag | BeautifulSoup, timezone: ZoneInfo | None) -> tuple[ActivityDate, ActivityDate]:
    opens, closes = ActivityDate(), ActivityDate()
    # lang=en is requested for each page, so labels are independent of the bot locale.
    for block in node.select('[data-region="activity-dates"] > div'):
        label = block.select_one("strong")
        if label is None:
            continue
        name = label.get_text(" ", strip=True).rstrip(":").casefold()
        value = _parse_date(block, timezone)
        if name in {"opens", "opened", "açılış", "açıldı"}:
            opens = _merge_date(opens, value)
        elif name in {"due", "closes", "closed", "son tarih", "kapanış"}:
            closes = _merge_date(closes, value)
    return opens, closes


def parse_course_activities(html: str, course: EdersCourse, timezone: ZoneInfo | None = None) -> list[EdersActivity]:
    soup = _page(html)
    if soup.select_one("#region-main .course-content") is None:
        raise EdersParseError("Missing eders course content")
    activities: dict[tuple[ActivityKind, int], EdersActivity] = {}
    timezone = _account_timezone(soup) or timezone
    for item in soup.select(".course-content li.activity"):
        section_node = item.find_parent("li", class_="section")
        heading = section_node.select_one(".sectionname") if section_node else None
        section = heading.get_text(" ", strip=True) if heading else ""
        content = item.select_one(".activity-altcontent")
        description = content.get_text(" ", strip=True) if content else ""
        if "modtype_label" in item.get_attribute_list("class"):
            match = re.fullmatch(r"module-(\d+)", str(item.get("id", "")))
            if match and description:
                identifier = int(match[1])
                activities[ActivityKind.LABEL, identifier] = EdersActivity(
                    identifier,
                    course,
                    ActivityKind.LABEL,
                    description[:300],
                    f"{EDERS_BASE_URL}/course/view.php?id={course.id}#module-{identifier}",
                    section=section,
                    description=description,
                )
            continue
        link = item.select_one(".activityname a[href], .activityinstance a[href]")
        href = link.get("href") if link else None
        if link is None or not isinstance(href, str):
            continue
        try:
            url = safe_eders_url(href, {f"/mod/{kind.value}/view.php" for kind in ActivityKind})
        except EdersUnsafeUrlError:
            continue
        kind = ActivityKind(urlsplit(url).path.split("/")[2])
        name_node = item.select_one(".instancename")
        name = (name_node or link).get_text(" ", strip=True)
        # Access-hide labels are presentation text, not part of the activity title.
        if name_node:
            for hidden in name_node.select(".accesshide"):
                name = name.removesuffix(hidden.get_text(" ", strip=True)).strip()
        opens, closes = _dates(item, timezone)
        identifier = eders_id(url)
        activities[kind, identifier] = EdersActivity(
            identifier, course, kind, name, url, opens, closes, section=section, description=description
        )
    return list(activities.values())


def _assignment_status(soup: BeautifulSoup) -> tuple[SubmissionStatus, GradingStatus]:
    submission = SubmissionStatus.UNKNOWN
    if soup.select_one(".submissionstatussubmitted"):
        submission = SubmissionStatus.SUBMITTED
    elif soup.select_one(".submissionstatusdraft"):
        submission = SubmissionStatus.DRAFT
    elif soup.select_one(".submissionstatusnew, .submissionstatusreopened"):
        submission = SubmissionStatus.NOT_SUBMITTED
    else:
        for row in soup.select(".submissionstatustable tr"):
            label, value = row.select_one("th"), row.select_one("td")
            if (
                label
                and value
                and label.get_text(" ", strip=True) == "Submission status"
                and value.get_text(" ", strip=True)
                in {"No attempt", "Nothing has been submitted for this assignment", "No submissions have been made yet"}
            ):
                submission = SubmissionStatus.NOT_SUBMITTED
    grading = GradingStatus.UNKNOWN
    if soup.select_one(".submissiongraded"):
        grading = GradingStatus.GRADED
    elif soup.select_one(".submissionnotgraded"):
        grading = GradingStatus.NOT_GRADED
    return submission, grading


def _quiz_status(soup: BeautifulSoup) -> tuple[SubmissionStatus, GradingStatus]:
    # A completed attempt confirms that attempt's submission, not completion of the
    # entire quiz. An active later attempt takes precedence. Hidden grades stay unknown.
    table = soup.select_one("table.quizattemptsummary")
    modern = soup.select("table.quizreviewsummary")
    if modern:
        attempts = []
        for summary in modern:
            fields = {}
            for row in summary.select("tr"):
                label, cell = row.select_one("th"), row.select_one("td")
                if label and cell:
                    fields[label.get_text(" ", strip=True).casefold()] = cell.get_text(" ", strip=True)
            attempts.append(_attempt_status(fields.get("status", ""), fields.get("grade", "")))
        return _latest_attempt(attempts)
    if table is None:
        return SubmissionStatus.UNKNOWN, GradingStatus.UNKNOWN
    headers = [cell.get_text(" ", strip=True).casefold() for cell in table.select("thead th")]
    status_index = next((i for i, value in enumerate(headers) if value in {"state", "status"}), None)
    if status_index is None:
        return SubmissionStatus.UNKNOWN, GradingStatus.UNKNOWN
    grade_index = next((i for i, value in enumerate(headers) if value.startswith("grade")), None)
    states: list[tuple[SubmissionStatus, GradingStatus]] = []
    for row in table.select("tbody tr"):
        cells = row.select(":scope > td")
        if len(cells) <= status_index:
            continue
        value = cells[status_index].get_text(" ", strip=True).casefold()
        grade_text = ""
        if grade_index is not None and grade_index < len(cells):
            grade_text = cells[grade_index].get_text(" ", strip=True)
        states.append(_attempt_status(value, grade_text))
    return _latest_attempt(states)


def _attempt_status(value: str, grade_text: str) -> tuple[SubmissionStatus, GradingStatus]:
    state = SubmissionStatus.UNKNOWN
    if value.casefold().startswith("finished"):
        state = SubmissionStatus.SUBMITTED
    elif value.casefold().startswith("in progress"):
        state = SubmissionStatus.IN_PROGRESS
    grade = GradingStatus.UNKNOWN
    if grade_text.casefold() == "not yet graded":
        grade = GradingStatus.NOT_GRADED
    elif re.fullmatch(r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?", grade_text):
        grade = GradingStatus.GRADED
    return state, grade


def _latest_attempt(states: list[tuple[SubmissionStatus, GradingStatus]]) -> tuple[SubmissionStatus, GradingStatus]:
    for state, grade in reversed(states):
        if state == SubmissionStatus.IN_PROGRESS:
            return state, grade
    return states[-1] if states else (SubmissionStatus.UNKNOWN, GradingStatus.UNKNOWN)


def parse_activity_details(html: str, activity: EdersActivity, timezone: ZoneInfo | None = None) -> EdersActivity:
    soup = _page(html)
    timezone = _account_timezone(soup) or timezone
    body = soup.select_one("body")
    expected = f"page-mod-{activity.kind.value}-view"
    if body is None or body.get("id") != expected:
        raise EdersParseError("Unexpected eders activity page")
    opens, closes = _dates(soup.select_one("#region-main") or soup, timezone)
    for row in soup.select(".submissionstatustable tr"):
        label, value = row.select_one("th"), row.select_one("td")
        if label and value and label.get_text(" ", strip=True).casefold() in {"due date", "extension due date"}:
            closes = _merge_date(closes, _parse_date(value, timezone))
    opens = _merge_date(activity.opens, opens)
    closes = _merge_date(activity.closes, closes)
    submission, grading = _assignment_status(soup) if activity.kind == ActivityKind.ASSIGNMENT else _quiz_status(soup)
    mismatch = False
    if closes.instant is not None:
        for day, month, year in re.findall(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", activity.name):
            try:
                title_date = datetime(int(year), int(month), int(day), tzinfo=UTC).date()
                mismatch |= title_date != closes.instant.date()
            except ValueError:
                pass
    return replace(
        activity, opens=opens, closes=closes, submission=submission, grading=grading, title_date_mismatch=mismatch
    )
