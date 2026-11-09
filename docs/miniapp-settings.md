# Mini App settings and course selection

Inline Telegram Web App buttons open `/app/?view=settings` or `/app/?view=courses`.
Both views are available to registered users regardless of achievement access.
Without `MANASHELPER_PUBLIC_URL`, use the bot's native settings and course selection.

Every API request requires `Authorization: tma <signed Telegram initData>`.
Authentication uses the configured bot token and the same expiration checks as achievements.
The authenticated Telegram user is the only account read or changed. Request bodies
must not contain a user ID. API responses use `Cache-Control: no-store`.

| Method | Path | Input |
| --- | --- | --- |
| GET | `/api/settings` | None |
| PUT | `/api/settings/notifications` | `setting`: `schedule_changes`, `exam_grades`, or `lesson_skips`; `enabled`: boolean |
| PUT | `/api/settings/food` | `weekday`: integer 0–6 (Monday–Sunday); `meal`: `lunch` or `dinner`; `enabled`: boolean |
| PUT | `/api/settings/eders` | `setting`: `day_before`, `two_hours_before`, `openings`, `deadline_changes`, `hide_archived`, or `new_materials`; `enabled`: boolean |
| PUT | `/api/settings/broadcast` | `muted`: boolean |
| GET | `/api/studies/faculties` | None |
| GET | `/api/studies/departments` | Query: `faculty_id` UUID |
| GET | `/api/studies/courses` | Query: `department_id` UUID |
| PUT | `/api/studies/courses/{course_id}` | `tracked`: boolean |

Settings reads and successful writes return `locale`, the saved bot `theme`, localized `ui` strings,
`notifications`, seven `food` day settings, `eders`, and `tracked_courses`.
Catalog reads return `faculties`, `departments`, or `courses` arrays.
Eders settings are `null` when disabled; writing them returns 404.

Writes reuse the owning feature's use cases and serialize on the user's database row.
They set explicit values, so retries do not toggle values again. Repeating an active
broadcast mute preserves its existing deadline; a new mute lasts 14 days.
The bot and Mini App share saved preferences and tracked courses.
The Mini App uses the saved bot theme for copy and the Pick me or Dead inside colour palette;
Telegram's light/dark preference remains independent. Choose the bot theme under Settings → Theme.

Missing or invalid authentication returns 401; an unregistered user returns 403.
Invalid JSON, extra body fields, invalid enum values, non-boolean flags, out-of-range
weekdays, and malformed catalog identifiers return 400. An unknown course returns 404.
