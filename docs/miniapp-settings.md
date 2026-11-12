# Mini App settings and course selection

Inline Telegram Web App buttons open `/app/settings` or `/app/courses`.
Vue Router uses HTML5 history under `/app/`; direct requests and reloads serve the same application shell.
Old `/app/?view=settings` and `/app/?view=courses` links redirect while preserving other query parameters.
Settings/course navigation updates the URL, so browser Back/Forward restores the selected view.
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
| GET | `/api/studies/free-time` | Query: `course_ids`, 1–8 comma-separated positive course IDs |

Settings reads and successful writes return `locale`, the saved bot `theme`, localized `ui` strings,
`notifications`, seven `food` day settings, `eders`, and `tracked_courses`.
Catalog reads return `faculties`, `departments`, or `courses` arrays. Courses and tracked courses include
`level` (`bachelor`, `master` or `doctorate`); graduate programmes are labelled by name, not by year 5/6.

`/app/free-time` (opened from the bot's timetable) compares any registered user's selected courses,
for example their own and their friends'. The selection lives in `?courses=1,2` so the page can be
reloaded or shared; without it the page starts from the viewer's tracked courses. The endpoint returns
`max_courses`, the selected `courses` (with department, faculty and level, duplicates removed) and five
`days` (`weekday` 1–5) with `windows` of consecutive periods free for every course: `start`, `end`
("H:MM") and `periods`. Periods are the distinct timetable periods of all synchronized courses.
Eders settings are `null` when disabled; writing them returns 404.

Writes reuse the owning feature's use cases and serialize on the user's database row.
They set explicit values, so retries do not toggle values again. Repeating an active
broadcast mute preserves its existing deadline; a new mute lasts 14 days.
The bot and Mini App share saved preferences and tracked courses.
The Mini App uses the saved bot theme for copy and the Pick me or Dead inside colour palette;
Telegram's light/dark preference remains independent. Choose the bot theme under Settings → Theme.

Missing or invalid authentication returns 401; an unregistered user returns 403.
Invalid JSON, extra body fields, invalid enum values, non-boolean flags, out-of-range
weekdays, malformed catalog identifiers, and an empty, malformed or oversized free-time selection
return 400. An unknown course returns 404.
