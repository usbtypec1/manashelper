import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from manashelper.db.models.eders import EdersNotification
from manashelper.repositories.eders_repository import EdersRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.eders_models import ActivityKind, EdersActivity, EdersSnapshot, SubmissionStatus
from manashelper.services.eders_serialization import deserialize_snapshot, serialize_snapshot
from manashelper.services.obis import UserNotFoundError


class EdersSetting(StrEnum):
    DAY_BEFORE = "day_before"
    TWO_HOURS_BEFORE = "two_hours_before"
    OPENINGS = "openings"
    DEADLINE_CHANGES = "deadline_changes"
    HIDE_ARCHIVED = "hide_archived"


@dataclass(frozen=True, slots=True)
class EdersSettings:
    day_before: bool
    two_hours_before: bool
    openings: bool
    deadline_changes: bool
    hide_archived: bool


@dataclass(frozen=True, slots=True)
class EdersEvent:
    key: str
    activity: EdersActivity
    event_type: str
    event_time: datetime
    due_at: datetime
    previous_deadline: datetime | None = None


def activity_key(activity: EdersActivity) -> str:
    return f"{activity.kind.value}:{activity.id}"


def _event(
    activity: EdersActivity, kind: str, time: datetime, due: datetime, old: datetime | None = None
) -> EdersEvent:
    identity = f"{activity_key(activity)}:{kind}:{time.isoformat()}:{old.isoformat() if old else ''}"
    if kind == "changed":
        # A -> B -> A -> B is three distinct changes, even when dates repeat.
        identity = f"{identity}:{due.isoformat()}"
    return EdersEvent(hashlib.sha256(identity.encode()).hexdigest(), activity, kind, time, due, old)


def plan_events(snapshot: EdersSnapshot, previous: EdersSnapshot | None, settings: EdersSettings) -> list[EdersEvent]:
    old = {activity_key(item): item for item in previous.activities} if previous else {}
    events = []
    now = snapshot.fetched_at
    for activity in snapshot.activities:
        if activity.kind not in {ActivityKind.ASSIGNMENT, ActivityKind.QUIZ}:
            continue
        key = activity_key(activity)
        before = old.get(key)
        closes, opens = activity.closes.instant, activity.opens.instant
        if (
            settings.deadline_changes
            and before
            and closes
            and before.closes.instant
            and closes != before.closes.instant
            and closes > now
        ):
            events.append(_event(activity, "changed", closes, now, before.closes.instant))
        if activity.submission == SubmissionStatus.SUBMITTED:
            continue
        if closes and closes > now and not activity.closes.conflict:
            for enabled, hours in ((settings.day_before, 24), (settings.two_hours_before, 2)):
                due = closes - timedelta(hours=hours)
                # Baseline and newly discovered activities don't backfill old reminders.
                if enabled and (due > now or (before and previous and previous.fetched_at <= due)):
                    events.append(_event(activity, f"before_{hours}", closes, due))
        if (
            settings.openings
            and opens
            and not activity.opens.conflict
            and (closes is None or closes > now)
            and (opens > now or (before and previous and previous.fetched_at <= opens))
        ):
            events.append(_event(activity, "opened", opens, opens))
    return events


class EdersTrackingService:
    def __init__(self, eders_repository: EdersRepository, user_repository: UserRepository) -> None:
        self._repository = eders_repository
        self._users = user_repository

    async def get_settings(self, user_id: int) -> EdersSettings:
        if await self._users.get_by_id(user_id) is None:
            raise UserNotFoundError(user_id)
        state = await self._repository.get_state(user_id)
        return EdersSettings(*(getattr(state, item.value) for item in EdersSetting))

    async def toggle(self, user_id: int, setting: EdersSetting) -> EdersSettings:
        await self.get_settings(user_id)
        state = await self._repository.get_state(user_id)
        setattr(state, setting.value, not getattr(state, setting.value))
        return await self.get_settings(user_id)

    async def observe(self, user_id: int, marker: str, snapshot: EdersSnapshot) -> EdersSnapshot:
        settings = await self.get_settings(user_id)
        state = await self._repository.get_state(user_id)
        previous = (
            deserialize_snapshot(state.snapshot) if state.snapshot and state.credential_marker == marker else None
        )
        if previous and previous.fetched_at >= snapshot.fetched_at:
            return previous
        old = {activity_key(item): item for item in previous.activities} if previous else {}
        snapshot = replace(
            snapshot,
            activities=tuple(
                replace(
                    item,
                    first_seen=old[activity_key(item)].first_seen
                    if activity_key(item) in old
                    else (snapshot.fetched_at if previous else None),
                )
                for item in snapshot.activities
            ),
        )
        planned = {}
        for event in plan_events(snapshot, previous, settings):
            key = hashlib.sha256(f"{marker}:{event.key}".encode()).hexdigest()
            planned[key] = replace(event, key=key)
        existing = await self._repository.get_notifications(user_id)
        stored = {event.event_key: event for event in existing}
        current = {activity_key(item): item for item in snapshot.activities}
        for stored_event in existing:
            item = current.get(stored_event.activity_key)
            valid_change = (
                stored_event.event_type == "changed" and item and item.closes.instant == stored_event.event_time
            )
            valid_reminder = (
                item
                and item.submission != SubmissionStatus.SUBMITTED
                and (
                    (
                        stored_event.event_type == "before_24"
                        and settings.day_before
                        and item.closes.instant == stored_event.event_time
                    )
                    or (
                        stored_event.event_type == "before_2"
                        and settings.two_hours_before
                        and item.closes.instant == stored_event.event_time
                    )
                    or (
                        stored_event.event_type == "opened"
                        and settings.openings
                        and item.opens.instant == stored_event.event_time
                    )
                )
            )
            if previous is None or (stored_event.event_key not in planned and not valid_change and not valid_reminder):
                stored_event.cancelled = True
            elif item:
                stored_event.payload = serialize_snapshot(EdersSnapshot((item,), snapshot.fetched_at))
        for key, event in planned.items():
            if key in stored:
                if stored[key].sent_at is None:
                    stored[key].cancelled = False
                    stored[key].payload = serialize_snapshot(EdersSnapshot((event.activity,), snapshot.fetched_at))
                continue
            self._repository.add_notification(
                EdersNotification(
                    user_id=user_id,
                    event_key=key,
                    activity_key=activity_key(event.activity),
                    event_type=event.event_type,
                    event_time=event.event_time,
                    due_at=event.due_at,
                    payload=serialize_snapshot(EdersSnapshot((event.activity,), snapshot.fetched_at)),
                    previous_deadline=event.previous_deadline,
                )
            )
        state.snapshot = serialize_snapshot(snapshot)
        state.credential_marker = marker
        return snapshot

    async def pending_events(self, user_id: int, now: datetime) -> list[EdersEvent]:
        settings = await self.get_settings(user_id)
        rows = await self._repository.get_notifications(user_id)
        candidates = []
        for row in rows:
            if row.cancelled or row.sent_at or row.due_at > now:
                continue
            enabled = {
                "before_24": settings.day_before,
                "before_2": settings.two_hours_before,
                "opened": settings.openings,
                "changed": settings.deadline_changes,
            }[row.event_type]
            activity = deserialize_snapshot(row.payload).activities[0]
            if (
                not enabled
                or (activity.closes.instant and activity.closes.instant <= now)
                or (row.event_type == "opened" and now - row.event_time > timedelta(days=1))
            ):
                row.cancelled = True
                continue
            candidates.append(
                EdersEvent(row.event_key, activity, row.event_type, row.event_time, row.due_at, row.previous_deadline)
            )
        # If a prolonged outage crossed both thresholds, deliver the nearest reminder.
        nearer = {activity_key(event.activity) for event in candidates if event.event_type == "before_2"}
        for row in rows:
            if row.event_type == "before_24" and row.activity_key in nearer:
                row.cancelled = True
        return [
            event
            for event in candidates
            if event.event_type != "before_24" or activity_key(event.activity) not in nearer
        ]

    async def mark_sent(self, user_id: int, key: str, now: datetime) -> None:
        for event in await self._repository.get_notifications(user_id):
            if event.event_key == key:
                event.sent_at = now
                return

    async def get_poll_user_ids(self) -> list[int]:
        return await self._repository.get_poll_user_ids()
