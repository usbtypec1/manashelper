# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Manashelper is a Telegram bot (Python 3.13, aiogram 3, SQLAlchemy 2 async, Dishka DI) for Manas University
students. There is **no REST API** — all user interaction happens through Telegram long-polling.

This is a from-scratch Python rewrite of a former Java/Spring Boot implementation. Timetable browsing, the
cafeteria daily menu, OBIS grade/attendance lookup, and lesson-change notifications have been ported; the
"About" screens from the original Java bot have not been ported yet (see Roadmap below).

Core capabilities (current):

- **Faculty/department/course catalog browsing** via inline keyboards, backed by Postgres.
- **Per-user course tracking**: tapping a course toggles tracking it (✅) via a `user_courses` join table.
- **Cafeteria daily menu**: scraped menu with dish photos/calories and per-user ratings.
- **OBIS integration**: an aiogram FSM conversation collects a student's OBIS credentials, verifies them against
  the real OBIS login before saving (AES-GCM encrypted at rest), and lets the user fetch their current exam
  grades and lesson-attendance/skip-budget summary on demand — see `services/obis.py`,
  `scraping/obis_client.py`, `scraping/obis_parser.py`, `bot/routers/obis.py`.
- **Notification settings**: a `⚙️ Settings` menu (`bot/routers/settings.py`) lets each user toggle five
  notification kinds (schedule changes, before-lunch/before-dinner menu pings, exam-grade changes, lesson skips),
  backed by a lazily-created `NotificationSettings` row per user that defaults every toggle to enabled — see
  `services/notification_settings.py`.
- **Scheduled notifications** (the `jobs/` package, wired up in `main.py`): the daily menu is broadcast to
  opted-in users at 11:00/17:00 Bishkek time; OBIS exam grades and lesson attendance are polled hourly per user
  and diffed against previously-seen state to notify only on actual changes; each tracked course's timetable is
  scraped hourly and diffed to notify trackers of schedule changes — see "Scheduled jobs & change detection"
  below.
- **Localization**: every user-facing string is served through aiogram's built-in gettext-based i18n, with the
  user's locale auto-detected from Telegram, falling back to Russian — see "Localization (i18n)" below.
- `/start` resolves the user's locale, upserts the Telegram user, and shows the main reply keyboard.
- **Advertising platform (барахолка)**: an aiogram FSM (`bot/routers/advertisement.py`) collects a title,
  description, optional price/media/expiry, gated by a mandatory-contact check (Telegram username or a saved
  phone number), then submits the ad for moderation to a single shared moderation chat
  (`Settings.moderation_chat_id`) with Approve/Reject buttons (`bot/routers/advertisement_moderation.py`) — there
  is no per-user moderator role; anyone acting from that configured chat is authorized. Approving publishes the
  ad to a configured Telegram channel (`Settings.advertisement_channel_id`) rather than an in-bot browse feed,
  with contact details hidden behind a `/start ad_<id>` deep link (opens the bot, reveals the seller's contacts,
  and is logged), and rejecting can carry an optional comment shown to the ad's owner. Users manage their own ads
  (paginated list, detail, delete) under "📋 My ads" and their saved phone numbers under "⚙️ Settings → 📱 My
  phone numbers"; an hourly job (`jobs/advertisement.py::cleanup_expired_advertisements_job`) deletes ads past
  their `expires_at` (chosen from fixed presets, not free text), removing their channel post(s) first — see
  "Advertising platform"
  below.

## Commands

Dependency management is via `uv`. Run from the repo root:

```
uv sync                                                # install dependencies + create .venv
uv run alembic upgrade head                            # apply migrations (also runs automatically on app boot)
uv run alembic revision --autogenerate -m "message"    # generate a new migration from model changes
uv run python -m manashelper.main                      # run the bot locally (needs env vars below + Postgres)
uv run pytest                                          # run tests (needs the dev Postgres running, and compiled
                                                        # gettext catalogs — see below)
uv run ruff check .                                    # lint
uv run ruff format .                                   # format
uv run mypy src/manashelper                            # type check
```

Gettext catalog workflow (see "Localization (i18n)" below for the full picture):

```
uv run pybabel extract -F babel.cfg -o src/manashelper/locales/messages.pot --no-location src
                                                        # scan source for _()/ngettext() calls -> .pot template
uv run pybabel update -i src/manashelper/locales/messages.pot -d src/manashelper/locales
                                                        # merge new/changed source strings into every locale's .po
uv run pybabel compile -d src/manashelper/locales      # .po -> .mo (must be re-run after editing any .po by hand;
                                                        # required before running the app or the test suite)
```

Checkstyle-equivalent strictness: `ruff` enforces a 120-char line length, import ordering, no unused/wildcard
imports, PEP8 naming, and pyupgrade rules (`pyproject.toml` → `[tool.ruff]`). `mypy --strict` runs over
`src/manashelper` (not `tests/` or `alembic/versions/`, which are excluded from strict typing/line-length rules
respectively — see `pyproject.toml`/`[tool.ruff] extend-exclude`).

### Running locally

The app needs Postgres and these environment variables (see `src/manashelper/config.py`): `TELEGRAM_BOT_TOKEN`,
`DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD`, `OBIS_ENCRYPTION_KEY` (a base64-encoded 32-byte
AES-256 key used by `CryptoService` to encrypt stored OBIS passwords — generate one with
`python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"`), `ADVERTISEMENT_CHANNEL_ID`
(the chat id of the Telegram channel approved ads are published to — the bot must be an admin of that channel
with post rights), `MODERATION_CHAT_ID` (the chat id of the group/chat that receives new ads to
Approve/Reject — the bot must be a member with permission to send messages there; anyone acting from this chat
is treated as authorized, see "Advertising platform" below), and optionally `DATASOURCE_HOST` (defaults to `db`,
the docker-compose service name — set to `localhost` for local dev outside Docker). `docker-compose.dev.yml`
starts only Postgres, exposed on host port `5432`. A local `.env` file (gitignored) is read automatically via
`pydantic-settings`.

CI/CD (`.github/workflows/ci-cd.yml`): the `test` job (lint + type-check + tests against a Postgres service
container) runs on every push to every branch, as well as on PRs targeting `main` and on `v*` tag pushes. Two more
jobs only run after `test` passes on a push directly to `main` or a `v*` tag: `build` builds the Docker image
(`docker/Dockerfile`) and pushes `usbtypec1/manashelper:<version>` / `:latest` to Docker Hub, exposing the version
as a job output (`steps.version.outputs.version`, from `$GITHUB_OUTPUT` — job outputs, not env vars, are how a
later job reads a value computed in an earlier one); `deploy` (`needs: build`, so it's skipped whenever `build` is)
then SSHes into the deploy host to pull `usbtypec1/manashelper:${{ needs.build.outputs.version }}` and restart via
`docker compose up -d`, followed by `docker image prune -af` to drop old, no-longer-referenced versioned app images
(`docker-compose.yml` pins the `app` service to a specific `:<version>` tag each deploy, so without `-a` only
dangling/untagged images would be cleaned and old version tags would keep accumulating on disk).

## Architecture

### Package layout (by layer, not by feature)

Under `src/manashelper/`, code is organized by technical layer, mirroring the original Java structure:
`bot/routers` (aiogram handlers), `bot/keyboards` (inline keyboard builders), `bot/middlewares`, `bot/callback_data.py`,
`services` (business logic), `repositories` (SQLAlchemy queries), `db/models` (ORM models), `jobs` (`AsyncIOScheduler`
job functions, one module per feature area — see "Scheduled jobs & change detection" below), `config.py`, `di.py`,
`main.py`. As with the Java version, expect this to stay flat-by-layer rather than gaining per-feature
subpackages as more of the roadmap gets ported.

**Services return plain dataclasses, never ORM models.** A `service` method called from a `bot/routers` handler
returns a frozen `dataclass` (e.g. `FacultyModel`, `DepartmentSummary`, `CourseSummary`) or raises, never a
SQLAlchemy model instance — routers must never hold an ORM object. Map ORM model → dataclass with a private
module-level helper next to the service class (see `course._to_summaries`, used by `CourseService`).

**`services/` classes exist to hold DI-injected collaborators, not as Java-style ceremony.** A `*Service` class's
`__init__` takes the repositories (and other collaborators, e.g. `CryptoService`, `ObisClient`) it needs and
stores them as attributes; its methods are the only thing a router or a `jobs/` module depends on via
`FromDishka[...]`/`request_container.get(...)` — the presentation layer never sees a repository, an `AsyncSession`,
or `Settings` directly, only the service. Pure helper logic that doesn't touch `self` (formatting, mapping a
scraped/ORM object to a dataclass) is a private module-level function, not a `@staticmethod` — see
`course._to_summaries` or `obis._to_exams_model`.

### Telegram update handling (aiogram routers)

Each feature area is an aiogram `Router` (`bot/routers/start.py`, `bot/routers/timetable.py`), included into the
`Dispatcher` in `main.py`. Unlike the old Java chain-of-responsibility (`shouldHandle`/`handle` over a flat handler
list, first match wins), aiogram matches each incoming update against filters declared on `@router.message(...)` /
`@router.callback_query(...)` decorators — still effectively first-match-wins across included routers, so keep
filters mutually exclusive the same way the Java handlers' `shouldHandle` predicates had to be.

Callback data is packed via aiogram's typed `CallbackData` factories (`bot/callback_data.py` —
`FacultyCallback`/`DepartmentCallback`/`CourseCallback`), replacing the old `CallbackDataByIdFilter.pack`/
`.parseUUID`/`.parseInt` string convention — `SomeCallback.filter()` is passed directly to
`@router.callback_query(...)`, and the parsed instance is injected into the handler as a `callback_data: SomeCallback`
parameter.

### Concurrency: per-chat ordering

aiogram's `Dispatcher.start_polling` dispatches each update as its own `asyncio` task by default
(`handle_as_tasks=True`), so two updates from the *same* chat could run concurrently unless something serializes
them. `bot/middlewares/per_chat_ordering.py::PerChatOrderingMiddleware` (registered as an outer middleware on both
`dispatcher.message` and `dispatcher.callback_query`) holds one `asyncio.Lock` per chat id so a chat's updates
process strictly in order — this matters because `CourseService.toggle_tracked_course`'s tracked-courses
read-modify-write isn't safe under concurrent access for the same user. This is the Python analog of the Java
`TelegramConsumer`'s per-chat `CompletableFuture` chaining over a virtual-thread executor.

### Dependency injection (Dishka)

`di.py` defines two providers: `AppProvider` (`Scope.APP` — `Settings`, the `AsyncEngine`, the
`async_sessionmaker`, created once per process) and `RequestProvider` (`Scope.REQUEST` — one `AsyncSession` per
update, plus repositories/services built on top of it). `setup_dishka(container, dispatcher)` +
`inject_router(dispatcher)` in `main.py` wire dependency injection into router handlers via `FromDishka[X]`
parameter annotations — the analog of Spring's constructor injection into `@Component`/`@Service` beans. The
`RequestProvider`'s session provider commits on success and rolls back on exception, giving each update
transactional semantics equivalent to Spring's `@Transactional`.

**Do not use `dishka.integrations.aiogram.setup_dishka(..., auto_inject=True)`.** As of dishka 1.10.1 + aiogram
3.31, it registers its handler-injection pass as a `router.startup` callback via
`functools.partial(inject_router, router=router, ...)`, but aiogram's `Router.emit_startup` always injects its own
`router=self` kwarg into every startup callback — colliding with the partial's bound `router` kwarg and raising
`TypeError: inject_router() got multiple values for argument 'router'`. Instead call
`setup_dishka(container, dispatcher)` (no `auto_inject`) followed by an explicit `inject_router(dispatcher)`, as
done in `main.py` — confirmed working end-to-end against a real dispatcher, including through to a genuine
Telegram API call.

### Data layer

Alembic (`alembic/versions/*.py`) is the source of truth for schema — this is a fresh start, not a port of the old
Flyway migration history, though the seed data (faculties/departments/courses) was carried over from the Java
project's `V2__seed_faculties_and_departments.sql` into `e82d16133698_seed_faculties_departments_courses.py`.
`alembic/env.py` points `target_metadata` at `manashelper.db.base.Base.metadata` and overrides `sqlalchemy.url`
from `Settings.database_url` at runtime — `alembic.ini`'s `sqlalchemy.url` placeholder is never actually used.
Migrations run automatically on boot (`main.py::run_migrations`, called before `asyncio.run(main())` — mirrors the
old `FlywayConfig`'s `initMethod=migrate` bean) as well as being runnable manually via `uv run alembic upgrade head`.

Add new migrations with `uv run alembic revision --autogenerate -m "..."` after changing a model under
`db/models/`, rather than hand-writing schema changes.

### Tests

`tests/conftest.py` provides a `session` fixture: each test runs inside a transaction opened on a dedicated
connection, with the `AsyncSession` bound via `join_transaction_mode="create_savepoint"` so that even if the code
under test calls `session.commit()`, only a SAVEPOINT is released — the outer transaction is always rolled back
after the test, so tests can freely insert rows (including ones that collide in shape with seeded catalog data,
as long as ids don't collide) without polluting the dev database. Tests run against the real dev Postgres
(`docker-compose.dev.yml`), not SQLite — avoids dialect drift on native `UUID`/`TIMESTAMP` types.

### OBIS integration notes

`ObisClient` (`scraping/obis_client.py`) opens a fresh `httpx.AsyncClient` per call (base URL
`https://obistest.manas.edu.kg`, `follow_redirects=True`) rather than keeping a persistent per-chat session like
the Java `ObisSession`/`ObisSessionManager` did — OBIS is re-authenticated on every attendance/exam-grade fetch
anyway (see `ObisService`), so there is no session reuse to preserve, and this avoids an unbounded
`dict[chat_id, session]` growing for the process lifetime. Credentials are collected via an aiogram FSM
(`bot/routers/obis.py::ObisCredentialsForm`, `MemoryStorage` — fine for a single-process deployment; move to
`RedisStorage` if the bot ever runs multi-worker) rather than the Java version's external Telegram WebApp form,
and are verified against a real OBIS login before being persisted. Passwords are encrypted at rest with AES-GCM
(`CryptoService`) instead of the Java version's raw AES-ECB.

### Localization (i18n)

All user-facing text is translated via aiogram's built-in `aiogram.utils.i18n` (a thin wrapper over GNU gettext,
requiring the `Babel` package — see the `aiogram[i18n]` extra in `pyproject.toml`). Source strings are written in
English directly at each call site as `_("...")` (`from aiogram.utils.i18n import gettext as _`) or, for
count-dependent text, `ngettext(singular, plural, n)` — never behind a lookup table or an f-string-interpolated
variable, because Babel's extractor only records a literal string argument, not whatever a variable happens to
hold. Compiled catalogs live at `src/manashelper/locales/<locale>/LC_MESSAGES/messages.{po,mo}` for `ru`/`ky`/`tr`;
English has **no catalog at all** — `I18n.gettext` already falls back to the raw (English) msgid when a locale or
a specific message isn't found, so shipping a redundant identity catalog would just be more to keep in sync.
`*.po` files are the hand-translated source of truth and are committed; `*.mo` files are compiled build artifacts
and are gitignored (compiled by `docker/Dockerfile` and by CI — see Commands above — anyone running the bot or
test suite locally must run `pybabel compile` after cloning or after editing a `.po` file).

`localization/locale.py::Locale` is the supported-locale enum (`ky`/`ru`/`en`/`tr`); `localization/i18n.py` holds
the single process-wide `I18n` instance. `User.locale` (nullable `String(2)`) persists a user's resolved locale.
`bot/middlewares/i18n.py::LocaleMiddleware` (registered *after* `setup_dishka` in `main.py`, so it can use the
request-scoped container) runs on every update: it upserts the user via `services/locale.py::LocaleService`,
which returns the saved locale if there is one, otherwise auto-detects one from
`message.from_user.language_code` (`localization/locale.py::resolve_from_language_code`), falling back to
`DEFAULT_LOCALE` (Russian) when that language code is missing or unsupported — the resolution always succeeds,
so there is no picker shown on this path. The middleware then enters `i18n.context()` / `i18n.use_locale(...)`
and calls the handler inside it, so every `_()`/`ngettext()` call made anywhere during that update — filters,
handlers, keyboards, formatters — resolves against the right locale via the contextvar aiogram's `I18n` keeps,
with no `Translator`/locale parameter threaded through call signatures. `bot/filters/translated_text.py`
(`TranslatedText`) exists because a reply-keyboard button's label is only known once translated, so matching the
incoming message text against a hardcoded string (`F.text == "..."`) can't work across locales.

Jobs (the `jobs/` package) run outside any Telegram update, so there's no ambient middleware to set the gettext
context; each per-recipient send there looks up that user's `Locale` and wraps its own `format_...(...)` call in
`with i18n.context(), i18n.use_locale(locale.value): ...` explicitly. A user can still change their locale
explicitly at any time via `/language` or the "🌐 Language" row in Settings (`bot/routers/locale.py`), which
shows the 4-language picker (`bot/keyboards/locale.py`) — the only place that picker is shown, now that
auto-detection never falls through to it.

### Scheduled jobs & change detection

`src/manashelper/jobs/` holds every `AsyncIOScheduler` job function registered in `main.py::main`, one module per
feature area (`jobs/food_menu.py`, `jobs/obis_notification.py`, `jobs/timetable_sync.py`,
`jobs/scheduled_message_deletion.py`, `jobs/advertisement.py`), plus `jobs/common.py` for cross-cutting helpers
shared by more than one job (`get_user_locale`, `send_notification`, `chunk`/`delete_message_batch` for batched
`deleteMessages` calls). Each job opens its own short-lived Dishka request scope(s)
(`async with container() as request_container`) rather than reusing one across the whole run, and wraps its body
in a broad `except Exception: logger.exception(...)` so one failure (a bad HTML page, a dead OBIS login, a user
who blocked the bot) never aborts the rest of the batch — the same resilience shape as the pre-existing
`sync_daily_menus_job`. Per-recipient Telegram sends are wrapped individually in `except TelegramAPIError` for
the same reason.

Three notification-producing jobs all follow one pattern: keep a Postgres table of the *last known state* per
(user or course, item), diff a freshly scraped/fetched snapshot against it, persist the new state, and only
notify on an actual difference (never on the first-ever observation, so enabling a setting doesn't dump a user's
entire history at them):

- **Timetable sync** (`services/timetable_sync.py`, hourly): `scraping/timetable_client.py` +
  `scraping/timetable_parser.py` scrape `http://timetable.manas.edu.kg/department-printer/{course_id}` (plain
  HTTP, no auth — the site has no HTTPS listener) for every `Course.id`, parsed into one `Lesson` row per
  (course, weekday, time slot) holding a normalized "code name — teacher, room" string; a changed/added/removed
  slot notifies every tracker with `schedule_changes_enabled`.
- **OBIS exam grades & lesson skips** (`services/obis_notification.py`, hourly, one poll per user):
  reuses `ObisService.get_exam_grades`/`get_attendance` (so it's re-login-per-poll like every other OBIS call),
  diffing against `UserExamGrade` (per user+lesson_code+exam_name) and `UserLessonAttendance` (per
  user+lesson_code) rows; a user with no saved OBIS credentials is skipped cheaply (a local DB check) before any
  network call, so polling every user hourly is safe.
- **Daily menu broadcast** (`jobs/food_menu.py::broadcast_lunch_menu_job`/`broadcast_dinner_menu_job`, cron
  11:00/17:00 `Asia/Bishkek`): re-sends the same media-group format used for an on-demand `/yemek` request to
  every user with `before_lunch_enabled`/`before_dinner_enabled`.

`NotificationSettingsRepository` centralizes "who should be notified": a user with no `NotificationSettings` row
yet (never opened the settings menu) counts as every toggle being enabled — the repository queries use
`LEFT JOIN ... WHERE column IS DISTINCT FROM FALSE`, not `= TRUE`, specifically so an absent row doesn't silently
opt a user out.

### Advertising platform

A from-scratch subsystem (no Java precedent) ported from `features/ADVERTISING_PLATFORM.md`. Notable design
choices, since none of these had an existing pattern to copy:

- **No per-user moderator role.** An earlier revision had a `User.role` column
  (`marketplace_admin`/`superadmin`, assigned by hand in Postgres); that was removed in favor of a single shared
  `Settings.moderation_chat_id`. Authorization for every moderation action is enforced by
  `bot/routers/advertisement_moderation.py::_is_moderation_chat` checking that the callback/message's
  `chat.id` matches that configured chat — not by anything stored per-user — so adding/removing moderators is
  purely a matter of who's a member of that Telegram chat.
- **No in-bot browse feed**: approved ads are published to a Telegram channel
  (`Settings.advertisement_channel_id`) instead of a bot-side listing screen a user could browse. Every
  `AdvertisementChannelMessage` row records a published message id so the channel post(s) can be removed again
  when the ad is deleted or expires (a media-group publish yields one message per photo/video).
- **SQL-side pagination**: `AdvertisementRepository.get_page_by_user_id` does real `LIMIT`/`OFFSET` pagination for
  "📋 My ads", unlike every other paginated screen in the bot (`versions.py`, `lesson_search.py`), which slices an
  already-fully-fetched in-memory list — a persistent management list needs to reflect deletes immediately.
- **User-uploaded media**: `bot/routers/advertisement.py`'s `AdvertisementForm.media` state is the only place in
  the bot that receives (rather than sends) Telegram photos/videos, storing each `file_id` in
  `AdvertisementMedia` (capped at 10 per ad, tracked in FSM state until submission). Sending a 10-item album
  delivers 10 separate updates, one per photo/video — rather than replying to each one, `_render_media_prompt`
  edits a single tracked message in place for the running count, relying on `PerChatOrderingMiddleware` already
  serializing every update for that chat (so there's no debounce/race handling to get wrong).
- **Contact gate**: posting is blocked until the user has at least one contact method. A Telegram username is
  read live off `User.username` (already kept fresh by `LocaleMiddleware`'s per-update upsert, so no extra Bot
  API call is needed); phone numbers are collected inline at the start of the posting flow (reply-keyboard
  `request_contact` button or manual entry, validated by `UserContactService.is_valid_phone_number`) and
  persisted in `UserPhoneNumber` — see `services/user_contact.py`. Users manage their saved numbers (add/delete)
  from `⚙️ Settings → 📱 My phone numbers` (`bot/routers/phone_numbers.py`), which reuses the same
  contact-request keyboard (`bot/keyboards/phone_numbers.py`) as the posting flow.
- **Contacts are hidden on the public channel post**, unlike the poster's own confirm preview and the
  moderation chat's review message (both closed audiences, which see raw contact details via
  `format_advertisement(..., contact=...)`). The channel post instead embeds a bot deep link
  (`format_advertisement(..., contact_deep_link=...)`, built from `bot.get_me()` in
  `advertisement_moderation.py::on_approve` as `https://t.me/<bot>?start=ad_<id>`). Opening it is handled by
  `bot/routers/advertisement_contact.py` (`CommandStart(deep_link=True)`, registered in `main.py` *before*
  `start_router` so a bare `/start` still falls through to the normal welcome flow) via
  `AdvertisementContactService.reveal_contact`, which also logs the open as an `AdvertisementContactView` row
  (never deduplicated — every open is its own row, for counting interest).
- **Expiration is chosen from fixed presets** (45 minutes / 6 hours / 24 hours / 7 days / no expiration —
  `AdvertisementExpiryCallback`), not free-text date entry.
- **HTML escaping**: `services/html_sanitization.py::escape_html` (a thin wrapper over aiogram's
  `html_decoration.quote`) is applied to every user-supplied field — title, description, rejection comment,
  contact username/phone — wherever it's interpolated into a message sent with the bot's default
  `ParseMode.HTML`. This is a correctness fix as much as a safety one: an unescaped bare `&`/`<`/`>` makes
  Telegram reject the whole `sendMessage`/`sendMediaGroup` call with "can't parse entities", so without this an
  ad titled e.g. "Fish & Chips" could never be published or even forwarded to moderators.
- **Locale correctness**: every message sent to a chat *other* than the one handling the current update (an
  owner notification, e.g.) must resolve its `_()` calls inside `i18n.use_locale(that_recipient's_locale)`, not
  the acting user's ambient locale — a builder function/closure evaluated *inside* the `with` block, not a
  pre-built string passed into it (a pre-built string is just inert data by the time
  `with i18n.use_locale(...):` wraps it — see `advertisement_moderation.py::_notify_owner`'s
  `build_text: Callable[[], str]` parameter). The moderation chat and the channel are both single shared
  destinations rather than a specific recipient, so both always render in `DEFAULT_LOCALE` instead
  (`advertisement.py::_notify_moderation_chat`, `advertisement_moderation.py::on_approve`).
- **Rate limiting**: `AdvertisementService.assert_can_post` caps a user at 5 ads/hour
  (`AdvertisementRepository.count_created_since`) — a data-driven business rule, distinct from the generic
  per-chat token-bucket throttle in `bot/middlewares/rate_limit.py`.
- **Moderation**: a new ad is sent once to `Settings.moderation_chat_id` with Approve/Reject buttons
  (`bot/routers/advertisement_moderation.py`); both actions re-check the ad is still `pending` before acting
  (`AdvertisementNotPendingError`) so two people tapping at once in that chat can't double-process the same ad.
- **Expiration cleanup**: `jobs/advertisement.py::cleanup_expired_advertisements_job` (hourly) deletes ads past
  `expires_at`, removing their channel post(s) first — same outbox-sweep shape as
  `jobs/scheduled_message_deletion.py::cleanup_scheduled_message_deletions_job`.

## Roadmap (not yet ported from the Java version)

- **About screens**: static informational callback handlers.
