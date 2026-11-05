import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup
from bs4.element import Tag

from manashelper.modules.obis.application.models import Transcript, TranscriptSemester
from manashelper.modules.obis.errors import ObisParseError


def decimal_value(value: str) -> Decimal:
    try:
        result = Decimal(value.strip().replace(",", "."))
        if not result.is_finite() or result < 0:
            raise ValueError("Invalid transcript value")
        return result
    except (ValueError, InvalidOperation) as error:
        raise ObisParseError("Invalid numeric transcript value") from error


def parse_transcript(html: str) -> Transcript:
    soup = BeautifulSoup(html, "lxml")
    semesters = []
    overall: Decimal | None = None
    for table in soup.select("table.table-striped"):
        rows = [row for row in table.select("tr") if row.find_parent("table") is table]
        if not rows:
            continue
        heading = rows[0].get_text(" ", strip=True)
        year = re.search(r"(\d{4})\s*-\s*(\d{4})", heading)
        if year is None:
            # The only non-semester table has the overall totals with three cells.
            cells = rows[-1].find_all("td", recursive=False)
            if len(cells) == 3:
                overall = decimal_value(cells[2].get_text())
            continue
        lower = heading.casefold()
        season = next(
            (
                key
                for key, words in (("fall", ("күз", "güz")), ("spring", ("жаз", "bahar")), ("summer", ("жай", "yaz")))
                if any(word in lower for word in words)
            ),
            None,
        )
        if season is None:
            raise ObisParseError("Unknown transcript semester")
        grades = []
        for row in rows:
            cells = row.find_all("td", recursive=False)
            if len(cells) == 5:
                grades.append(cells[2].get_text(strip=True).upper())
        credits: Decimal | None = None
        points: Decimal | None = None
        for nested in table.select("table"):
            for row in nested.select("tr"):
                cells = row.find_all("td", recursive=False)
                label = row.find("th", recursive=False)
                if len(cells) == 3 and isinstance(label, Tag):
                    # Semester-end totals, not a sum of unweighted course grades.
                    credits = decimal_value(cells[0].get_text())
                    points = decimal_value(cells[1].get_text())
                    decimal_value(cells[2].get_text())
        semesters.append(
            TranscriptSemester(f"{year.group(1)}-{year.group(2)}:{season}", credits, points, tuple(grades))
        )
    if not semesters or overall is None or overall > 4:
        raise ObisParseError("Transcript semesters or overall GPA not found")
    if len({semester.key for semester in semesters}) != len(semesters):
        raise ObisParseError("Duplicate transcript semester")
    # Academic year followed by fall, spring, summer; source column layout does
    # not determine chronological order.
    order = {"fall": 0, "spring": 1, "summer": 2}
    semesters.sort(key=lambda semester: (semester.key[:9], order[semester.key.split(":")[1]]))
    return Transcript(tuple(semesters), overall)
