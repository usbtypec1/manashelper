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
The Mini App uses the saved bot theme for copy. Pick me, Dead inside and GTA VI also apply their own
palettes in both Telegram appearances. Choose the bot theme under Settings → Theme.

Missing or invalid authentication returns 401; an unregistered user returns 403.
Invalid JSON, extra body fields, invalid enum values, non-boolean flags, out-of-range
weekdays, malformed catalog identifiers, and an empty, malformed or oversized free-time selection
return 400. An unknown course returns 404.

## Admin panel

With `MANASHELPER_PUBLIC_URL` configured, the bot installs a personal Telegram menu button
that opens `/app/admin` in each administrator's private chat. It sets the button at startup
and on the administrator's `/start`. Set `MANASHELPER_ADMIN_USER_IDS` to a JSON array of positive
Telegram user IDs. If unset, a positive `MANASHELPER_ADMIN_CHAT_ID` is the single allowed user.
A group chat ID gives no one access. An explicit empty array disables access.

`GET /api/admin/users` authenticates signed Telegram initData and checks the allowed user IDs
on every request. It returns up to 50 registered users ordered by Telegram ID, including users
who stopped the bot. Each entry contains `id` (a decimal string), `full_name`, nullable `username`,
`locale`, `theme` and `bot_stopped`. Search with `q` and filter by `locale`, `theme` or
`status` (`active` or `stopped`). Filters apply before pagination. Pass the returned
`next_cursor` as the `after` query parameter to read the next page with the same filters.
A null cursor marks the end. Invalid authentication returns 401, a user outside the allowlist
gets 403, and a malformed cursor returns 400. Responses use `Cache-Control: no-store`.

Telegram retains per-chat button settings. After an ID is removed from the allowlist, the API
denies its requests even if Telegram still shows its previously configured button.

The directory uses Telegram's live palette, MainButton to load more or retry, and
SecondaryButton to refresh when another page is available. At the end of the list,
refresh becomes the primary action. See the [Mini App interaction guidelines](miniapp-interactions.md).

### Broadcasts

`/app/admin/broadcasts` provides a composer, history and per-recipient delivery statuses. The picker
uses the user directory and preserves selections while searching. The audience is all eligible users,
only the chosen users, or all eligible users except the chosen users. Broadcast mutes, stopped bots
and quiet hours are enforced by the shared outbox. The editor sends text with Telegram's delivery
wrapper and the localized unsubscribe button.

Create at `POST /api/admin/broadcasts` with a client-generated UUID `id`, an `audience`
(`all`, `allowlist` or `blocklist`), decimal-string `user_ids` for an explicit list, and at least
one `variants` entry with `text`, optional `locale` and optional `theme`. Each language and theme
pair can appear once. The first matching variant wins in this order:

1. Exact language and theme.
2. Language only.
3. Theme only.
4. Unrestricted variant.
5. First configured variant.

The campaign and all queued deliveries commit together. Repeating the same request with the same ID
returns the previous result. Reusing an ID with different content or as another author returns 409.

- `GET /api/admin/broadcasts` returns history and counts by delivery status. Pass `next_cursor` as `before`.
- `GET /api/admin/broadcasts/{id}` includes the saved variants, audience and counts.
- `GET /api/admin/broadcasts/{id}/deliveries` shows Telegram IDs, statuses, attempts and error codes.
  Pass `next_cursor` as `after`.
- `POST /api/admin/broadcasts/{id}/retry` requeues failed, expired or cancelled deliveries for currently
  eligible recipients. It preserves the original messages and attempt counters. Sent and active work
  stay in place. The response includes the number requeued.

Delivered means Telegram accepted the message. History is retained across regular outbox cleanup.
