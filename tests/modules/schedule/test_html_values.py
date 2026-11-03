from datetime import datetime

import pytest

from manashelper.modules.schedule.application.lesson_search import LessonSearchResult
from manashelper.modules.schedule.application.schedule import ScheduleLessonModel
from manashelper.modules.schedule.application.timetable_sync import LessonChange
from manashelper.modules.schedule.presentation.lesson_search_formatter import format_lesson_search_page
from manashelper.modules.schedule.presentation.timetable_formatter import format_day_schedule, format_lesson_changes
from manashelper.platform.i18n.catalog import i18n


@pytest.fixture(autouse=True)
def locale_context():
    with i18n.context(), i18n.use_locale("en"):
        yield


def test_timetable_and_change_notifications_escape_source_content():
    content = "<i>Lesson</i> — Teacher & guest, <room>"
    timetable = format_day_schedule(1, [ScheduleLessonModel(1, "09:00-09:50", content)], datetime(2026, 11, 2, 9))
    changes = format_lesson_changes([LessonChange(1, "09:00-09:50", None, content)])
    for text in (timetable, changes):
        assert "<b>&lt;i&gt;Lesson&lt;/i&gt;</b>" in text
        assert "Teacher &amp; guest - &lt;room&gt;" in text
        assert "<i>" not in text


def test_search_escapes_all_source_fields():
    result = LessonSearchResult(1, 1, "<Faculty>", "A & B", 1, "<i>Lesson</i>", ["09:00-09:50 <extra>"])
    text = format_lesson_search_page([result], 0)
    assert "&lt;Faculty&gt;" in text and "A &amp; B" in text
    assert "&lt;i&gt;Lesson&lt;/i&gt;" in text and "&lt;extra&gt;" in text
