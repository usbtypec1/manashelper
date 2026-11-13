# AGENTS.md

Shared repository instructions for coding agents. Keep instructions here; `CLAUDE.md` imports this file for Claude Code.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for implementation details and rationale,
and [docs/BACKLOG.md](docs/BACKLOG.md) for deferred work. Check the code when documentation differs.

## Project

Manashelper is a Python 3.13 Telegram bot for Manas University students. It uses aiogram 3, async SQLAlchemy 2,
Postgres, Dishka dependency injection, Alembic, APScheduler and gettext. The entry point is `src/manashelper/main.py`.
With MANASHELPER_PUBLIC_URL it runs an aiohttp webhook, Mini App API and Vue static assets in the same process as
scheduler/outbox; without it, local polling is used. See [docs/gamification.md](docs/gamification.md) for setup,
achievement rules, HTTP contracts and verification.

Current features include the faculty/department/course catalog and course tracking, timetable and lesson search,
cafeteria menus, OBIS grades and attendance, notification settings, scheduled change notifications, advertisements
with moderation and a channel, feedback and admin broadcasts. Read the relevant
router, service, repository, and tests before changing a feature. `features/` holds some feature specifications.

## Architecture

Business features live in `modules/`; shared infrastructure lives in `core/` and `platform/`.
Within a feature's `infrastructure/`, keep ORM models in `models/` and repositories in `repositories/`.
Repository filenames use the entity name without `_repository` (for example, `repositories/user.py`);
class names retain the `Repository` suffix. Flat features without `infrastructure/` keep their existing layout.
The planned feature migration is complete. `bootstrap.py` explicitly loads ORM models; `jobs` keeps scheduler wiring,
and `core/time.py` owns the shared timezone. Schedule owns its application text normalization helper.
Empty legacy `bot/`, `services/`, `repositories/` and `scraping/` packages were removed.
Feedback and advertisements live in `modules/feedback/` and `modules/advertisements/`, with REQUEST providers in `main.py`.
Advertisements separates presentation, application and infrastructure, with domain enums.
Feedback keeps its flat persistence/presentation layout and owns application/use_cases plus FeedbackQuery.
The student survey and its response table are removed; only historical Alembic migrations remain.
Broadcast lives in `modules/broadcast/`: SendBroadcastUseCase uses active, unmuted IDs from NotificationRecipientsQuery and a delivery protocol;
Telegram localization, HTML and photo/text preparation stay in its sender adapter. Its provider retains REQUEST scope.
Broadcast accepts a text/photo draft and URL or existing callback buttons, with preview and explicit confirmation.
Each delivery adds a localized 14-day unsubscribe button. Notifications owns the timezone-aware
broadcast_muted_until setting, recipient filtering and early reset under Settings → Notifications.
User.bot_stopped is the shared persistent delivery flag. Recipient SQL, enqueueing and the outbox worker suppress
stopped users across broadcasts, Food menu, Schedule, OBIS and Eders; permanent errors set it in the worker scope.
A private-chat profile refresh clears it; group activity preserves it. Notification preferences and snapshot syncs stay intact.
Background messages use `platform/telegram/outbox/`, provided by REQUEST-scoped OutboxProvider. Producers enqueue
in their existing transaction; an independent worker uses durable leases, SKIP LOCKED and shared PostgreSQL token
buckets. It retries 429 using retry_after, 5xx/network errors with exponential jittered backoff, and respects
expires_at. Cleanup runs daily and retains valid pending work. See `docs/outbox.md` for guarantees and TTLs.
Food menu lives in `modules/food_menu/` with application, presentation, infrastructure, jobs and provider.
Its client/parser retain APP scope; repositories, queries and use cases retain REQUEST. BroadcastFoodMenuUseCase selects
the menu/recipients, TelegramFoodMenuSender handles delivery, and jobs are thin request-scope entry points.
Schedule lives in `modules/schedule/`: catalog/tracking, timetable/search, sync, presentation, infrastructure and jobs.
TimetableClient remains APP; services/repositories remain REQUEST. CourseTrackingRepository owns the tracked-course
query formerly in UserRepository, preserving ORM collections. SyncCourseTimetableUseCase uses public NotificationRecipientsQuery;
its Telegram sender preserves per-recipient locale and delivery behavior. GetStudyWeekUseCase consumes its public application results.
Sync stores each slot's lessons as `timetable_lesson_items` (code, name, teacher, room plus folded lookup keys) next to the
unchanged slot content/history; slots stored before V32 are backfilled silently on their next sync. It also sets
Course.level from the page heading ("5/6 - sınıf LEE" = master/doctorate; Medicine's years 5/6 stay bachelor) and the
daily job mirrors the site's room catalog (capacities) into `timetable_rooms`. CampusQuery derives free rooms, room and
teacher timetables from these items; FreeTimeQuery serves the Mini App `/app/free-time`; SubjectTimetableQuery is the
public per-subject weekly timetable that OBIS attendance shows. Change notifications merge consecutive identical periods
and report room/teacher moves of the same lesson as such. Studies has Rooms and Teachers entries; `/now` and the
timetable's Now button show the current and next class.
Notifications lives in `modules/notifications/`: application/use_cases, settings, recipient queries, ORM, repository, callbacks,
keyboard and router. Its provider retains REQUEST scope. Settings checks users through UsersQuery;
Schedule and OBIS polling select recipients through NotificationRecipientsQuery. Shared Settings navigation
stays in `platform/telegram/`; Food menu/Eders preferences and OBIS polling remain owned by their features.
NotificationSettingsRepository initializes all three flags to True when creating a row, before flush;
the first toggle disables the selected flag and summaries never expose transient None values.
Missing rows still opt recipients into all notifications. Do not rely on INSERT-time defaults when toggling new rows.
Shared weekday labels live in `localization/weekdays.py`; reuse `core/time.py::BISHKEK_TZ` instead of a feature's timezone.
Users lives in `modules/users/`: application locale/theme/status queries and use cases, infrastructure profile ORM and
repositories, presentation language/theme routers, keyboards and callbacks. UsersProvider retains REQUEST
scope for all its dependencies, including public UsersQuery (counts, IDs, existence). ResolveUserLocaleUseCase owns
profile refresh and locale resolution; LocaleQuery serves delivery reads. UsersQuery also exposes the current Telegram username.
User keeps OBIS credential columns and the Schedule tracked_courses relationship without schema changes.
OBIS owns credential access through ObisCredentialsRepository on the unchanged User row.
EdersQuery and RefreshEdersSnapshotUseCase read the student number without decrypting a password for direct login and cached snapshots.
Only a failed direct login triggers OBIS credential decryption and the legacy OBIS SSO fallback.
Eders tracking checks existence through UsersQuery; its repository owns credential eligibility SQL and the user-row lock.
Shared Telegram navigation lives in `platform/telegram/navigation.py`; feature routers must not import the start router for it.
The main keyboard groups academic features under Studies. Its reply submenu opens the timetable directly,
with Change courses in the first button row; subject search is a separate Studies entry. An untracked user
gets an explanation with a course-selection button. OBIS has Attendance and Grades; Eders has Materials
and Deadlines. Settings has no My lessons entry. All notification controls live under Settings → Notifications:
Schedule, OBIS, Food menu, Eders (when enabled) and broadcasts. Feature notification submenus return there.
OBIS credentials remain in general Settings. Settings navigation precedes feature FSM handlers and clears drafts.
The authenticated Mini App provides the same notification preferences and course selection to every registered
user, independently of gamification. Launch it using inline Web App buttons at `/app/settings` or
`/app/courses`. Vue Router owns Mini App navigation; `App.vue` only renders `RouterView`.
Legacy `/app/?view=...` links redirect to the corresponding route. Its idempotent API reuses owning use cases
and serializes mutations on the user's database row.
See `docs/miniapp-settings.md` for the contract. Never accept a client-provided user ID for these operations.
Eders/Study week stay hidden when disabled. Platform navigation and feature menu routers precede feature FSM handlers,
clearing unfinished forms on menu entry; the shared Back handler also serves Marketplace.
Keep feature code with its owner and limit changes to the requested scope. See `docs/ARCHITECTURE.md`
for current boundaries, `docs/MIGRATION.md` for the completed refactor and `docs/BACKLOG.md` for deferred work.
Add routers to the dispatcher in `platform/telegram/dispatcher.py`; features own their providers in the composition root.
Router order matters because aiogram uses the first matching handler; the
advertisement deep-link router must precede the plain `/start` router. Use typed `CallbackData` classes for inline
button payloads.

Routers and jobs depend on use cases, queries and shared application services, not repositories or `AsyncSession`.
Use cases own complete scenarios; shared services retain reusable application logic; repositories handle persistence.
Application boundaries return plain dataclasses, not ORM instances, to the
presentation layer. Put pure mapping and formatting helpers at module level. Escape user-provided and other dynamic
text with `platform/telegram/html.py::escape_html` before inserting it into Telegram HTML messages.

New or extracted use cases live in `application/use_cases/`: files use action names without a suffix
(for example, `save_obis_credentials.py`), classes use the `UseCase` suffix, and `execute()` is the single entry point.
Pure scenarios without state or injected dependencies may remain functions. Read-only operations may be grouped in queries.
Use `@dataclass(frozen=True, slots=True)` for application classes with injected dependencies, including queries and shared services.
Functions imported by another Python module are public and must not have a leading underscore; keep `_` for local helpers.
GetNotificationSettingsUseCase owns settings initialization; GetDailyMenuUseCase owns view-count updates.
Keep EdersTrackingService as the shared snapshot/event reconciliation component used by refresh and polling.

Core lives in `core/`: config.py, database.py, logging.py and provider.py. CoreProvider owns APP settings,
engine, session factory and the shared HTTP client, plus the REQUEST session. The last legacy `di.py` was removed;
StudyWeekProvider owns its REQUEST use case. Keep the single Base from `core/database.py`.
The `db` package was removed. Import ORM classes from their owning feature/platform modules, never from a global facade.
Call `bootstrap.load_models()` at application/test/Alembic bootstrap before using ORM. It registers all model modules and
configures string relationships without re-exporting classes. Standalone compositions must call it explicitly;
importing one repository no longer loads the whole schema as a side effect.
Telegram Platform lives in `platform/telegram/`: dispatcher, commands/catalog/extractor, navigation,
Settings callbacks/routers, filters, middleware, HTML/delivery and audit.
TelegramPlatformProvider owns audit repositories/services in REQUEST. Audit records only
matched/allowed updates from private chats only, masks password text with `[masked]`, and stays after the private-chat guard.
Scheduled message deletion and food menu auto-delete settings have been removed, including their tables.
Immediate message deletion remains available for advertisement publication removal.
The gettext adapter lives in `platform/i18n/catalog.py`; pure Locale/weekday labels stay in `localization/`.
Command JSON and .mo runtime directories are unchanged, with checkout/Docker-like path tests.
OBIS lives in `modules/obis/`: application queries/use cases/snapshot comparison, HTTP/parser/crypto,
credential and snapshot repositories/ORM, Telegram presentation, provider and jobs. ObisProvider keeps
ObisClient/CryptoService/ObisResultsSource in APP and all other dependencies in REQUEST. Public errors live in errors.py.
OBIS login requires a captcha. StartObisLoginUseCase opens a login form and returns its captcha image
(new credentials are encrypted first; without them it reuses the saved account); RefreshObisCaptchaUseCase opens
a fresh form; CompleteObisLoginUseCase submits the answer and saves credentials (resetting snapshots only when they
change) plus the session. ClearObisCredentialsUseCase removes credentials, snapshots/baselines and the session.
ObisSessions owns the AES-GCM encrypted session cookies in `obis_sessions`; polling and refreshes use them.
ObisCredentialsQuery owns credential reads/decryption; ObisResultsQuery reads cached results and eligible polling IDs.
RefreshObisGradesUseCase and RefreshObisAttendanceUseCase lock the user, fetch, persist snapshots, compare and save
notification baselines, returning data and changes. PollObisUserUseCase coordinates refresh and conditional delivery.
Use cases use application-owned ResultsSource and SnapshotStore protocols. ObisResultsSource owns HTTP/HTML
mapping; ObisSnapshotRepository owns JSON/ORM mapping and checks the account marker before decoding snapshots.
Application models live in application/models.py; attendance skip calculations stay in the application layer.
Credentials use CredentialsStore, ObisAuthenticator, SessionStore and PasswordCipher protocols; stored credential read models
hide both fields in repr. Notification comparisons are pure application functions returning changed baseline records
and notification events; ExamGradeStore/AttendanceStore persist those records without exposing ORM objects.
Its frozen read model hides secrets in repr; OBIS credentials retain the SHA-256 ciphertext marker.
Eders owns its HTTP client: try direct Moodle form login first, then the legacy OBIS login and /site/eders SSO flow
(OBIS now rejects that captcha-less fallback, so only direct Moodle login works).
PollObisUserUseCase handles expected auth/parse errors; its sender owns locale/HTML and enqueues messages transactionally.
Unexpected errors abort that user and are logged by the job, without stopping the next user.
The first grade snapshot and attendance's first row are silent. Later new or changed nonempty grades notify.
Saving completes the captcha login before assigning either credential field, so login/captcha/encryption failures
preserve both previous values and the previous session even if caught inside a committed scope. Only users with
a session are polled; when OBIS redirects a fetch to its login page, polling deletes the session and sends one
localized reminder with a login button (cached results stay visible). Preserve 15-minute polling (it also keeps
the session alive), FSM, password masking and encryption format.

OBIS and Eders user screens read persisted snapshots only, including Study week. Background jobs refresh both
every 15 minutes (Eders retains its existing interval override). Notification toggles affect delivery, not
synchronization. Missing snapshots show a preparation message; failed refreshes preserve the last successful data.
Snapshot reads must not acquire locks held during HTTP fetches. OBIS credential changes clear cached results
and comparison baselines; Eders validates its student-number marker.

Eders lives in `modules/eders/`: application snapshot/filter/tracking/polling, infrastructure client/parser/URL validation,
serialization/repository/ORM, Telegram presentation, jobs and provider. EdersProvider keeps the client APP and other
dependencies REQUEST. PollEdersUserUseCase preserves refresh→locale→pending→enqueue→ack ordering; its Telegram sender groups
materials and yields events after transactional handoff to the outbox. Queue failures abort only that user;
the outbox worker owns HTTP retries, expiration and permanent recipient failures. Preserve snapshot JSON, event keys, baseline/account/schema suppression,
monotonic observations, user-row FOR UPDATE before first state, and the one-retry whole-snapshot login flow.
The optional MANASHELPER_EDERS_PASSWORD env value is the shared Moodle password; obtain logintoken from the form for every login
and detect successful login by an authenticated page with sesskey, without a redirect URL allowlist.
Missing or empty MANASHELPER_EDERS_PASSWORD disables Eders and Study week routers,
main-menu buttons, Eders notification settings and polling. Legacy commands remain hidden aliases when enabled.
Eders polling requires only a nonempty saved student number; the snapshot marker is SHA-256 of that number.
The first sync after switching from the ciphertext marker establishes a silent account baseline.
Eders exceptions are public in `modules/eders/errors.py`; other features must not import them through HTTP/parser modules.

Study week lives in `modules/study_week/`: application models/helpers, application/use_cases, formatter.py, router.py and provider.py.
GetStudyWeekUseCase.execute reads Eders first, then Schedule, and derives the start date from the current Bishkek clock.
Only NoTrackedCoursesError becomes an empty timetable; other source errors propagate. The formatter covers seven local
calendar days, preserving sorting, HTML escaping, complete-line chunks and existing eders.* translation keys.
Its private `/week` router follows Eders immediately; Eders must not depend on Study week.

The session commits only on normal REQUEST finalization. An escaping body exception or cancellation triggers rollback;
commit failures/cancellation also trigger rollback before propagating. Dishka sends the scope exception as the yield value,
so CoreProvider must inspect it instead of relying only on except around yield. Caught errors inside a scope still allow commit.
Tests cover real PostgreSQL savepoints, aiogram's outer error handler, cancellation and cleanup failures in
`tests/core/test_core_transactions.py` and feature composition in `tests/modules/feedback/test_feedback_composition.py`.
New handlers use `FromDishka[...]`; jobs open request scopes with
`async with container() as request_container`. Keep `setup_dishka(container, dispatcher)` followed by an explicit
`inject_router(dispatcher)`; `auto_inject=True` conflicts with aiogram startup callbacks in the current versions.

`PerChatOrderingMiddleware` serializes updates from one chat, which protects flows that read and then change user
state. `RateLimitMiddleware` runs before it. `LocaleMiddleware` runs after Dishka setup so it can use the request
container. Keep middleware registration order and router filters in mind when adding handlers.

Feature tables use `obis_`, `advertisement_`, `food_`, `eders_` and `timetable_` prefixes. Shared user and
notification tables retain their names. Existing index and constraint names survive table renames.
Schema changes go through the owning feature's ORM and an Alembic migration in `alembic/versions`.
`bootstrap.load_models()` imports owned models for Alembic; add new ORM modules there. File relocation alone needs no schema migration.
Generate migrations with
`uv run python scripts/new_migration.py --autogenerate -m "description"` when a database is available, then review the generated
operations. `main.py` applies migrations on startup; `uv run alembic upgrade head` applies them manually.
New revision IDs and filenames use sequential V1, V2, ... numbers. The helper forwards standard Alembic
revision flags; omit `--autogenerate` for a handwritten migration. Never rewrite historical `revision` or
`down_revision` values: production databases already reference them. Renaming migration files is safe.

## Feature-specific conventions

- Gamification access is per-user and defaults off (`gamification_progress.enabled`; missing row means off).
  Only the configured admin chat can use `/gamification <Telegram user ID> on|off`.
  Disabled users must not accrue progress/awards, appear in ranking or access either gamification Mini App API.
  Authenticated settings and course-selection APIs remain available to registered users regardless of gamification access.
  The main reply-keyboard achievement button sends plain text; its handler replies with an inline Web App button
  so Telegram supplies signed initData. Never launch this authenticated Mini App from a reply-keyboard Web App button.
  Preserve their earned awards and progress. The extra transcript fetch is skipped while disabled.
  Eldin balasy counts three final AA grades within one semester; Thin ice counts five distinct subjects in one
  current attendance snapshot with theory OR practice absence >= 18.75%, counting each subject once.
  Iron attendance needs 0% in every reported percentage, only in Nov–Jan/Apr–Jun; Critic counts first ratings of 30 menus;
  Phoenix/Einstein/Stability use transcript course rows (see docs/gamification.md for exact rules).

- Food menu keeps rich/ephemeral message behavior, fixed-date callbacks and weekday meal
  notification settings. Its repository initializes new lunch/dinner flags to True before flush, so the first
  meal/day toggle disables the selection immediately. Missing rows mean enabled; saved preferences must be preserved.

- OBIS credentials are verified with a real captcha login before storage and encrypted with AES-GCM through
  `CryptoService`. The credentials form uses aiogram FSM and in-process `MemoryStorage`: student number, password,
  then a captcha photo. FSM keeps only plain pending-login values with the password encrypted. A wrong captcha or
  expired form (HTTP 400) shows a new captcha; wrong credentials restart at the student number. OBIS fetches reuse
  the saved session cookies and raise ObisSessionExpiredError when OBIS asks for a login.
  Grade/attendance pages use FSM caches keyed by message ID; page navigation must not re-fetch OBIS or mix results
  from different messages. Preserve expired-navigation handling after FSM data is cleared.
- All jobs are registered in `jobs/scheduler.py`. They use independent request scopes, catch
  failures per item or recipient, and log unexpected exceptions so one failure does not stop a batch. Grade,
  attendance and timetable notifications compare new snapshots with persisted last-known state.
  Attendance/timetable first observations and the first OBIS grade snapshot are silent.
  Users without a `NotificationSettings` row have all toggles enabled.
  Food menu, Schedule, OBIS and Eders jobs live in their modules. Schedule loads course IDs in one request scope,
  then opens another per course. TelegramAPIError skips a recipient; unexpected delivery/locale errors abort
  that course, are logged, and do not prevent the next course. Keep this boundary and the hourly Schedule job.
- Marketplace moderation is authorized by `Settings.moderation_chat_id`, not a user role. Approved ads go to the
  configured channel. Public posts hide contact details behind a `/start ad_<id>` link; contact opens are logged.
  The channel post IDs must remain available for deletion when an ad is removed or expires. The marketplace menu
  is a reply keyboard reached from its main-menu button or `/start market`.
  Expiry runs through `modules/advertisements/jobs.py` and `ExpireAdvertisementsUseCase`; the use case depends on its
  repository and `PublicationRemover`, while the Telegram adapter handles batching and best-effort failures.
  Preserve the contact gate, five-ads/hour limit, ten-media limit and pending-status checks for moderation.
  My ads uses SQL pagination; uploaded albums update one tracked prompt instead of replying to each item.
  Phone numbers belong to each advertisement, not to the user profile. Creation always asks for a number;
  skipping is allowed only with a current Telegram username and is rechecked by the application service.
  Advertisement.phone_numbers retains all historical saved numbers after migration; new ads store at most
  one entered number. The old phone-number settings and user_phone_numbers table have been removed.
- Feedback and `/broadcast` are restricted to `Settings.admin_chat_id`. Admins reply to forwarded feedback using
  Telegram's native reply action. `/broadcast` is registered only for that chat and sends to active registered users.
  Broadcast clears FSM before loading recipients and queues localized deliveries in the request transaction.
  The admin summary counts queued recipients. The outbox worker handles retries; locale lookup and queue failures
  abort without a summary and roll back queued work.

## Localization and Telegram text

Use stable message keys with literal `_("menu.settings")` or `ngettext(...)` arguments; dynamic strings and
f-strings are not extractable by Babel. Store all user-facing text in the English, Russian, Kyrgyz, Turkish and
Chinese (`zh`, simplified Chinese) `.po` catalogs under `src/manashelper/locales/`. English is the fallback
for missing translations; it must have a compiled catalog too. Preserve formatting placeholders in every translation. Use
`platform/telegram/filters/translated_text.py::TranslatedText` for reply-keyboard text filters rather than matching one
language's label directly.

`LocaleMiddleware` chooses a user's saved or Telegram-detected locale and falls back to Russian. Code sending a
message to another user must format it inside that recipient's `i18n.use_locale(...)` context; jobs must also
establish `i18n.context()` because they run outside update middleware. Shared moderation/admin chats and the
advertisement channel render in `DEFAULT_LOCALE`.
Evaluate translation calls and message builders inside the recipient's locale context; wrapping an already-built
string cannot change its language. Personal notifications also bind the recipient's saved Theme through i18n.use_theme;
never inherit another recipient's theme. Basic is the default. Theme copy lives in all five catalogs; decorate templates
before interpolating user content, and preserve dishes, photos, numbers, callback payloads and status meanings.

After editing a catalog, compile it with `.venv/bin/pybabel compile -d src/manashelper/locales`. The `.po` files
are committed; generated `.mo` files are ignored by Git. When adding msgids, use the extract/update workflow if
appropriate:

```sh
.venv/bin/pybabel extract -F babel.cfg -o src/manashelper/locales/messages.pot --no-location .
.venv/bin/pybabel update -i src/manashelper/locales/messages.pot -d src/manashelper/locales
.venv/bin/pybabel compile -d src/manashelper/locales
```

For a new private command, update `docs/commands/private.json` with its description's message key and add the
description to all five catalogs. `babel.cfg` includes a custom extractor for these JSON keys, so extraction
must run from the repository root with `.` as its input directory.
Check command definitions in `platform/telegram/command_catalog.py` and registration in `platform/telegram/commands.py` as well as the handler.

## Run and verify

Use `uv` for dependency management. From the repository root:

The frontend uses Bun 1.4.3 and `frontend/bun.lock`; follow [frontend/AGENTS.md](frontend/AGENTS.md)
for frontend conventions and verification. Use `bun install --cwd frontend --frozen-lockfile` to install
dependencies and `bun run --cwd frontend --bun build` to type-check and build the Mini App.

```sh
uv sync
uv run alembic upgrade head
uv run python -m manashelper.main
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/manashelper
.venv/bin/pytest
```

The app needs Postgres and the environment variables defined in `src/manashelper/core/config.py`: Telegram token,
database credentials, OBIS encryption key, advertisement channel ID/link, moderation chat ID and admin chat ID.
`MANASHELPER_DATASOURCE_HOST` defaults to the Docker service name `db`; use `localhost` when running outside Docker.
`docker/docker-compose.dev.yaml` starts the development Postgres on port 5432. A local `.env` is read automatically and
is ignored by Git.

For local verification, use a development `.env` with `MANASHELPER_TELEGRAM_BOT_TOKEN`, `MANASHELPER_OBIS_ENCRYPTION_KEY` and
the `MANASHELPER_DATASOURCE_NAME`, `MANASHELPER_DATASOURCE_USERNAME`, `MANASHELPER_DATASOURCE_PASSWORD` values matching the development database.
The commands below override the Docker hostname and provide placeholder Telegram chat/channel settings for tests:

```sh
docker compose --project-directory . --env-file .env -f docker/docker-compose.dev.yaml up -d --wait db
.venv/bin/pybabel compile -d src/manashelper/locales
env MANASHELPER_DATASOURCE_HOST=localhost \
  MANASHELPER_ADVERTISEMENT_CHANNEL_ID=-1000000000000 MANASHELPER_ADVERTISEMENT_CHANNEL_LINK=https://t.me/example \
  MANASHELPER_MODERATION_CHAT_ID=-1000000000001 MANASHELPER_ADMIN_CHAT_ID=-1000000000002 \
  .venv/bin/alembic upgrade head
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/manashelper
env MANASHELPER_DATASOURCE_HOST=localhost \
  MANASHELPER_ADVERTISEMENT_CHANNEL_ID=-1000000000000 MANASHELPER_ADVERTISEMENT_CHANNEL_LINK=https://t.me/example \
  MANASHELPER_MODERATION_CHAT_ID=-1000000000001 MANASHELPER_ADMIN_CHAT_ID=-1000000000002 \
  .venv/bin/pytest -q --tb=line
```

These commands target the local development database; do not point them at production.
For focused tests, append a test path to the same `env ... .venv/bin/pytest` command.

Tests mirror ownership: `tests/modules/<feature>/`, `tests/core/` and `tests/platform/{telegram,i18n}/`.
Run one feature with `tests/modules/eders/`, for example. Keep shared DB fixtures in `tests/conftest.py`,
resource roots in `tests/paths.py`, and shared Eders factories/fixture in its own test package; do not import helpers
from a test module. Data stays in `tests/fixtures/`, also used by local HTTP mocks. Test packages use standard imports.

Tests use a real Postgres instance, not SQLite, and need compiled gettext catalogs. The `session` fixture in
`tests/conftest.py` uses a transaction and savepoint so writes roll back after each test. Ruff uses a 120-character
line limit; mypy runs in strict mode for `src/manashelper`. If `uv run` cannot read the global uv cache in a
sandbox, use the existing `.venv/bin/` executables. Run focused tests while editing and the relevant lint,
format, type and test checks before finishing a code change.

# Tool usage policy

Prefer IDE MCP tools over shell commands whenever an equivalent MCP tool exists.

For codebase exploration:

- Use Index MCP for symbol lookup, usages, implementations, hierarchy, diagnostics, and semantic navigation.
- Do not use grep, rg, find, sed, awk, or similar shell commands for code discovery when Index MCP can answer the question.
- Prefer IDE diagnostics over running ad-hoc compiler or linter commands just to inspect errors.

For IDE operations:

- Use JetBrains MCP for run configurations, debugger operations, IDE actions, and project-aware operations.
- Prefer IDE run configurations over manually reconstructing the same command in the shell.

Use terminal commands when:

- no suitable MCP tool exists;
- the MCP tool fails or returns insufficient information;
- the task inherently requires CLI tooling;
- running Maven/Gradle/Docker/Git commands is explicitly appropriate.

When falling back from MCP to terminal, briefly state why.

## MCP priority

For code analysis, always try `intellij-index` MCP before using shell-based search.

Preferred order:

1. Index MCP
2. JetBrains IDE MCP
3. Native file tools
4. Shell/terminal as fallback

Do not use `rg`, `grep`, `find`, or filesystem traversal for:

- finding classes;
- finding methods;
- finding usages;
- finding implementations;
- resolving symbols;
- inspecting inheritance;
- checking IDE diagnostics;

when the Index MCP provides an equivalent operation.
