import json
from dataclasses import replace
from datetime import timedelta

import pytest

from manashelper.modules.eders.application.models import EdersSnapshot, SubmissionStatus
from manashelper.modules.eders.application.tracking import EdersSettings, plan_events
from manashelper.modules.eders.infrastructure.parser import parse_activity_details, parse_course_activities
from manashelper.modules.eders.infrastructure.serialization import deserialize_snapshot, serialize_snapshot
from tests.modules.eders.factories import NOW, item


@pytest.mark.parametrize(
    ("markup", "completed"),
    [
        (
            '<button data-action="toggle-manual-completion" data-toggletype="manual:undo" data-cmid="20">Done</button>',
            True,
        ),
        (
            '<button data-action="toggle-manual-completion" data-toggletype="manual:mark-done" '
            'data-cmid="20">Mark as done</button>',
            False,
        ),
        (
            '<button data-action="toggle-manual-completion" data-toggletype="manual:undo" '
            'data-cmid="20">Готово</button>',
            True,
        ),
        ('<div class="activity-completion">Done</div>', True),
        ('<div class="activity-completion">Mark as done</div>', False),
        (
            '<button data-action="toggle-manual-completion" data-toggletype="manual:undo" data-cmid="21">Done</button>',
            False,
        ),
        ('<div class="activity-altcontent">Done</div>', False),
    ],
)
def test_course_completion_is_read_from_its_own_control(markup, completed):
    activity = item()
    html = f"""<main id="region-main"><div class="course-content"><ul>
    <li class="activity"><div class="activityname"><a href="{activity.url}">Work</a></div>
    {markup}</li></ul></div></main>"""
    parsed = parse_course_activities(html, activity.course)[0]
    assert parsed.completed is completed
    assert parsed.manual_completion is (
        'data-action="toggle-manual-completion"' in markup and 'data-cmid="20"' in markup
    )
    assert parsed.submission == SubmissionStatus.UNKNOWN


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("action", [None, "manual:undo", "manual:mark-done"])
def test_details_preserve_course_completion_unless_an_explicit_control_overrides_it(initial, action):
    control = (
        f'<button data-action="toggle-manual-completion" data-toggletype="{action}" data-cmid="20">State</button>'
        if action
        else ""
    )
    html = f'<body id="page-mod-assign-view"><main id="region-main">{control}</main></body>'
    parsed = parse_activity_details(html, item(completed=initial))
    assert parsed.completed is (initial if action is None else action == "manual:undo")
    assert parsed.submission == SubmissionStatus.UNKNOWN


def test_completion_round_trip_and_legacy_snapshot():
    snapshot = EdersSnapshot((item(completed=True, manual_completion=True),), NOW)
    assert deserialize_snapshot(serialize_snapshot(snapshot)) == snapshot
    legacy = json.loads(serialize_snapshot(snapshot))
    del legacy["activities"][0]["completed"]
    del legacy["activities"][0]["manual_completion"]
    assert not deserialize_snapshot(json.dumps(legacy)).activities[0].completed
    assert not deserialize_snapshot(json.dumps(legacy)).activities[0].manual_completion


def test_completed_activity_has_no_deadline_or_opening_events():
    previous = EdersSnapshot((item(),), NOW)
    activity = item(completed=True, closes=replace(item().closes, instant=NOW + timedelta(days=4)))
    current = EdersSnapshot((activity,), NOW + timedelta(hours=1))
    assert plan_events(current, previous, EdersSettings(True, True, True, True, True)) == []


async def test_completion_cancels_existing_reminders_and_reopening_can_schedule_them(tracking):
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW))
    await tracking.observe(980_001, "a", EdersSnapshot((item(completed=True),), NOW + timedelta(hours=1)))
    assert await tracking.pending_events(980_001, NOW + timedelta(days=2)) == []
    await tracking.observe(980_001, "a", EdersSnapshot((item(),), NOW + timedelta(hours=2)))
    assert {event.event_type for event in await tracking.pending_events(980_001, NOW + timedelta(days=2))} == {
        "opened",
        "before_24",
    }
