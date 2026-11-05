from decimal import Decimal

import pytest

from manashelper.modules.obis.errors import ObisParseError
from manashelper.modules.obis.infrastructure.transcript_parser import parse_transcript

# Synthetic values with the same nested table layout as the supplied transcript.
# The user's original HTML, profile, CSRF token and course history are not copied.
from tests.paths import FIXTURES_DIR

HTML = (FIXTURES_DIR / "obis/transcript.html").read_text()


def test_nested_semester_totals_and_unfinished_semester():
    result = parse_transcript(HTML)
    assert result.overall_gpa == Decimal("3.20")
    assert result.semesters[0].key == "2025-2026:spring"
    assert result.semesters[0].grades == ("F1", "FF")
    assert result.semesters[0].credits == 30
    assert result.semesters[0].points == 90
    assert result.semesters[1].credits is None


@pytest.mark.parametrize(
    "html", ["<form>Login</form>", HTML.replace("3,20", "NaN"), HTML.replace("90</td>", "oops</td>")]
)
def test_missing_or_malformed_transcript_is_not_an_empty_success(html):
    with pytest.raises(ObisParseError):
        parse_transcript(html)
