"""Optional exhaustive check against the local, private export (never committed)."""

import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
from lxml import html as lhtml

from manashelper.modules.eders.application.models import ActivityKind, EdersCourse, EdersSnapshot
from manashelper.modules.eders.infrastructure.parser import parse_account_timezone, parse_course_activities
from manashelper.modules.eders.infrastructure.serialization import deserialize_snapshot, serialize_snapshot


def test_saved_course_html_corpus():
    directory = Path(os.environ.get("EDERS_HTML_DIR", "r"))
    files = sorted(directory.glob("*.html"))
    if not files:
        pytest.skip("Local Eders export is absent; set EDERS_HTML_DIR")
    counts = Counter()
    deadlines = 0
    for path in files:
        source = path.read_text(encoding="utf-8")
        course = EdersCourse(int(path.stem.rsplit("_", 1)[1]), "Course")
        items = parse_course_activities(source, course)
        tree = lhtml.fromstring(source)
        # Independent DOM inventory: every supported module card must be represented.
        expected = set()
        for node in tree.xpath('//li[contains(concat(" ", normalize-space(@class), " "), " activity ")]'):
            kinds = {kind.value for kind in ActivityKind if f"modtype_{kind.value}" in node.get("class", "").split()}
            if not kinds:
                continue
            kind = kinds.pop()
            if kind == "label":
                content = node.xpath(
                    './/*[contains(concat(" ", normalize-space(@class), " "), " activity-altcontent ")]'
                )
                if not content or not content[0].text_content().strip():
                    continue
            elif not node.xpath('.//a[contains(@href, concat("/mod/", $kind, "/view.php?id="))]', kind=kind):
                continue  # Restricted activities may have no link for this student.
            expected.add((kind, int(node.get("id").removeprefix("module-"))))
        actual = {(entry.kind.value, entry.id) for entry in items}
        assert actual == expected, f"Module inventory differs in {path.name}: {expected ^ actual}"
        assert len(actual) == len(items), path.name
        timezone = parse_account_timezone(source)
        for entry in items:
            if entry.opens.source_text or entry.closes.source_text:
                assert not timezone or entry.opens.instant or entry.closes.instant, path.name
            if entry.closes.instant:
                deadlines += 1
            assert "sesskey" not in entry.url
            counts[entry.kind.value] += 1
        snapshot = EdersSnapshot(tuple(items), datetime.now(UTC), courses=(course,))
        assert deserialize_snapshot(serialize_snapshot(snapshot)) == snapshot, path.name
    print(f"Eders corpus: {len(files)} pages; activities={dict(counts)}; parsed deadlines={deadlines}")
