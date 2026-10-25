# AGENTS.md

Shared repository instructions for coding agents. Keep instructions here; `CLAUDE.md` imports this file for Claude Code.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for implementation details and rationale,
and [docs/BACKLOG.md](docs/BACKLOG.md) for deferred work. Check the code when documentation differs.

## Project

Manashelper is a Python 3.13 Telegram bot for Manas University students. It uses aiogram 3, async SQLAlchemy 2,
Postgres, Dishka dependency injection, Alembic, APScheduler and gettext. There is no REST API. The entry point is
`src/manashelper/main.py`; users interact with the bot through Telegram long polling.

Current features include the faculty/department/course catalog and course tracking, timetable and lesson search,
cafeteria menus, OBIS grades and attendance, notification settings, scheduled change notifications, advertisements
with moderation and a channel, feedback and admin broadcasts, and `/donate` with bank QR codes. Read the relevant
router, service, repository, and tests before changing a feature. `features/` holds some feature specifications.

## Architecture

Business features live in `modules/`; shared infrastructure lives in `core/` and `platform/`.
The planned feature migration is complete. `bootstrap.py` explicitly loads ORM models; `jobs` keeps scheduler wiring,
and `core/time.py` owns the shared timezone. Schedule owns its application text normalization helper.
Empty legacy `bot/`, `services/`, `repositories/` and `scraping/` packages were removed. Feedback, advertisements and the survey live in
`modules/feedback/`, `modules/advertisements/` and `modules/student_questions/`, with REQUEST providers in `main.py`.
Advertisements separates presentation, application and infrastructure, with domain enums; feedback and the survey stay flat.
Release history lives in flat `modules/versions/`, with functions and no artificial DI provider. Its runtime
`docs/versions/` path is tested for both checkout and Docker-like layouts.
Donations lives in flat `modules/donations/`: catalog, Telegram QR adapter, application service and presentation.
Its provider keeps DonationQrService in APP for shared bounded caching and DonationService in REQUEST.
Broadcast lives in flat `modules/broadcast/`: SendBroadcast uses UsersQuery and a delivery protocol;
Telegram localization, HTML and API errors stay in its sender adapter. Its provider retains REQUEST scope.
Food menu lives in `modules/food_menu/` with application, presentation, infrastructure, jobs and provider.
Its client/parser retain APP scope; repositories and services retain REQUEST. BroadcastFoodMenu selects
the menu/recipients, TelegramFoodMenuSender handles delivery/cleanup, and jobs are thin request-scope entry points.
Schedule lives in `modules/schedule/`: catalog/tracking, timetable/search, sync, presentation, infrastructure and jobs.
TimetableClient remains APP; services/repositories remain REQUEST. CourseTrackingRepository owns the tracked-course
query formerly in UserRepository, preserving ORM collections. SyncCourseTimetable uses public NotificationRecipientsQuery;
its Telegram sender preserves per-recipient locale and delivery behavior. GetStudyWeek consumes its public application results.
Notifications lives in flat `modules/notifications/`: settings, recipient queries, ORM, repository, callbacks,
keyboard and router. Its provider retains REQUEST scope. Settings checks users through UsersQuery;
Schedule and OBIS polling select recipients through NotificationRecipientsQuery. Shared Settings navigation
stays in `platform/telegram/`; Food menu/Eders preferences and OBIS polling remain owned by their features.
NotificationSettingsRepository initializes all three flags to True when creating a row, before flush;
the first toggle disables the selected flag and summaries never expose transient None values.
Missing rows still opt recipients into all notifications. Do not rely on INSERT-time defaults when toggling new rows.
Shared weekday labels live in `localization/weekdays.py`; reuse `core/time.py::BISHKEK_TZ` instead of a feature's timezone.
Users lives in `modules/users/`: application locale/contact services, infrastructure profile/phone ORM and
repositories, presentation language/phone routers, keyboards and callbacks. UsersProvider retains REQUEST
scope for all its dependencies, including public UsersQuery (counts, IDs, existence). LocaleService is the
shared user-locale boundary for middleware and delivery; UserContactService supplies plain contact models.
User keeps OBIS credential columns and the Schedule tracked_courses relationship without schema changes.
OBIS owns credential access through ObisCredentialsRepository on the unchanged User row.
EdersService reads plain credentials and an opaque marker through ObisCredentialsService; it no longer reads ORM/ciphertext.
Eders tracking checks existence through UsersQuery; its repository owns credential eligibility SQL and the user-row lock.
Shared Telegram navigation lives in `platform/telegram/navigation.py`; feature routers must not import the start router for it.
Keep feature code with its owner and limit changes to the requested scope. See `docs/ARCHITECTURE.md`
for current boundaries, `docs/MIGRATION.md` for the completed refactor and `docs/BACKLOG.md` for deferred work.
Add routers to the dispatcher in `platform/telegram/dispatcher.py`; features own their providers in the composition root.
Router order matters because aiogram uses the first matching handler; the
advertisement deep-link router must precede the plain `/start` router. Use typed `CallbackData` classes for inline
button payloads.

Routers and jobs depend on services, not repositories or `AsyncSession`. Services hold injected collaborators and
business logic; repositories handle persistence. Services return plain dataclasses, not ORM instances, to the
presentation layer. Put pure mapping and formatting helpers at module level. Escape user-provided and other dynamic
text with `platform/telegram/html.py::escape_html` before inserting it into Telegram HTML messages.

Core lives in `core/`: config.py, database.py, logging.py and provider.py. CoreProvider owns APP settings,
engine, session factory and the shared HTTP client, plus the REQUEST session. The last legacy `di.py` was removed;
StudyWeekProvider owns its REQUEST use case. Keep the single Base from `core/database.py`.
The `db` package was removed. Import ORM classes from their owning feature/platform modules, never from a global facade.
Call `bootstrap.load_models()` at application/test/Alembic bootstrap before using ORM. It registers all model modules and
configures string relationships without re-exporting classes. Standalone compositions must call it explicitly;
importing one repository no longer loads the whole schema as a side effect.
Telegram Platform lives in `platform/telegram/`: dispatcher, commands/catalog/extractor, navigation,
Settings callbacks/routers, filters, middleware, HTML/delivery, audit and scheduled message deletions.
TelegramPlatformProvider owns both audit and deletion repositories/services in REQUEST. Audit records only
matched/allowed updates, masks password text with `[masked]`, and stays after the private-chat guard.
Cleanup jobs use MessageDeletionService.delete_due with async delivery; delete_messages batches by 100,
continues after TelegramAPIError and propagates unexpected errors. Rows are acknowledged after all chats;
an unexpected sweep failure logs and leaves them queued. Preserve the five-minute schedule and no retry.
The gettext adapter lives in `platform/i18n/catalog.py`; pure Locale/weekday labels stay in `localization/`.
Command JSON and .mo runtime directories are unchanged, with checkout/Docker-like path tests.
OBIS lives in `modules/obis/`: application facade/credentials/snapshot comparison/polling, HTTP/parser/crypto,
credential and snapshot repositories/ORM, Telegram presentation, provider and jobs. ObisProvider keeps
ObisClient/CryptoService in APP and all other dependencies in REQUEST. Public errors live in errors.py.
ObisService retains save/has/clear/get methods; ObisCredentialsService owns verification/storage/decryption.
Its frozen read model hides secrets in repr; Eders marker stays SHA-256 of ciphertext, not plaintext.
The shared login/new_http_client functions are public OBIS infrastructure reused by Eders with the same cookies.
PollObisUser handles expected auth/parse errors; Telegram sender owns locale/HTML and skips TelegramAPIError.
Unexpected errors abort that user and are logged by the job, without stopping the next user.
Preserve two characterized behaviors: first nonempty grades notify immediately; attendance's first row is silent.
Saving assigns student_number before encryption, so an encryption error leaves that in-memory assignment changed.
Treat changes to these behaviors as separate fixes; see `docs/BACKLOG.md`. Preserve hourly scheduling, FSM,
password masking and encryption format.

Eders lives in `modules/eders/`: application snapshot/filter/tracking/polling, infrastructure client/parser/URL validation,
serialization/repository/ORM, Telegram presentation, jobs and provider. EdersProvider keeps the client APP and other
dependencies REQUEST. PollEdersUser preserves refresh→locale→pending→send→ack ordering; its Telegram sender groups
materials and yields delivered events for immediate acknowledgement. TelegramAPIError skips one message without ack;
unexpected errors abort only that user. Preserve snapshot JSON, event keys, baseline/account/schema suppression,
monotonic observations, user-row FOR UPDATE before first state, and the one-retry whole-snapshot SSO flow.
Eders exceptions are public in `modules/eders/errors.py`; other features must not import them through HTTP/parser modules.

Study week is flat `modules/study_week/`: application.py, formatter.py, router.py and provider.py.
GetStudyWeek.execute reads Eders first, then Schedule, and derives the start date from the current Bishkek clock.
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

Schema changes go through the owning feature's ORM and an Alembic migration in `alembic/versions`.
`bootstrap.load_models()` imports owned models for Alembic; add new ORM modules there. File relocation alone needs no schema migration.
Generate migrations with
`uv run alembic revision --autogenerate -m "description"` when a database is available, then review the generated
operations. `main.py` applies migrations on startup; `uv run alembic upgrade head` applies them manually.

## Feature-specific conventions

- Food menu keeps rich/ephemeral message behavior, fixed-date callbacks, per-chat cleanup and weekday meal
  notification settings. Its repository initializes new lunch/dinner flags to True before flush, so the first
  meal/day toggle disables the selection immediately. Missing rows mean enabled; saved preferences must be preserved.

- OBIS credentials are verified with a real login before storage and encrypted with AES-GCM through
  `CryptoService`. The credentials form uses aiogram FSM and in-process `MemoryStorage`. OBIS fetches authenticate
  per call; do not assume a persistent browser session.
  Grade/attendance pages use FSM caches keyed by message ID; page navigation must not re-fetch OBIS or mix results
  from different messages. Preserve expired-navigation handling after FSM data is cleared.
- All jobs are registered in `jobs/scheduler.py`. They use independent request scopes, catch
  failures per item or recipient, and log unexpected exceptions so one failure does not stop a batch. Grade,
  attendance and timetable notifications compare new snapshots with persisted last-known state.
  Attendance/timetable first observations are silent; OBIS's first nonempty grade currently notifies.
  A decision about changing that behavior is deferred in `docs/BACKLOG.md`.
  Users without a `NotificationSettings` row have all toggles enabled.
  Food menu, Schedule, OBIS and Eders jobs live in their modules. Schedule loads course IDs in one request scope,
  then opens another per course. TelegramAPIError skips a recipient; unexpected delivery/locale errors abort
  that course, are logged, and do not prevent the next course. Keep this boundary and the hourly schedule.
- Marketplace moderation is authorized by `Settings.moderation_chat_id`, not a user role. Approved ads go to the
  configured channel. Public posts hide contact details behind a `/start ad_<id>` link; contact opens are logged.
  The channel post IDs must remain available for deletion when an ad is removed or expires. The marketplace menu
  is a reply keyboard reached from its main-menu button or `/start market`.
  Expiry runs through `modules/advertisements/jobs.py` and `ExpireAdvertisements`; the use case depends on its
  repository and `PublicationRemover`, while the Telegram adapter handles batching and best-effort failures.
  Preserve the contact gate, five-ads/hour limit, ten-media limit and pending-status checks for moderation.
  My ads uses SQL pagination; uploaded albums update one tracked prompt instead of replying to each item.
- The student survey requires explicit confirmation before replacing a completed response. Persist the replacement
  only after the new survey finishes; cancellation leaves the old response intact. Callback session IDs reject stale
  buttons. Its deep-link router must precede the advertisement deep-link router, which claims other start payloads.
- Feedback and `/broadcast` are restricted to `Settings.admin_chat_id`. Admins reply to forwarded feedback using
  Telegram's native reply action. `/broadcast` is registered only for that chat and sends to all registered users.
  Broadcast clears FSM before loading recipients and sends sequentially without retry. TelegramAPIError during
  delivery skips that recipient; locale lookup failures and unexpected errors abort without a summary.
- `docs/requisites/` holds `/donate` bank QR images. Filenames provide bank labels. `DonationQrService` reuses
  Telegram file IDs with bounded LRU caching. If runtime data is added under `docs/`, copy its directory in
  `docker/Dockerfile`.
  The catalogue and QR adapter now live in `modules/donations/catalog.py` and `qr.py`; preserve the runtime
  directory and the APP scope when changing them. Donation and broadcast counts/IDs use public UsersQuery.

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
string cannot change its language.

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
`DATASOURCE_HOST` defaults to the Docker service name `db`; use `localhost` when running outside Docker.
`docker-compose.dev.yml` starts the development Postgres on port 5432. A local `.env` is read automatically and
is ignored by Git.

For local verification, use a development `.env` with `TELEGRAM_BOT_TOKEN`, `OBIS_ENCRYPTION_KEY` and
the `DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD` values matching the development database.
The commands below override the Docker hostname and provide placeholder Telegram chat/channel settings for tests:

```sh
docker compose -f docker-compose.dev.yml up -d --wait db
.venv/bin/pybabel compile -d src/manashelper/locales
env DATASOURCE_HOST=localhost \
  ADVERTISEMENT_CHANNEL_ID=-1000000000000 ADVERTISEMENT_CHANNEL_LINK=https://t.me/example \
  MODERATION_CHAT_ID=-1000000000001 ADMIN_CHAT_ID=-1000000000002 \
  .venv/bin/alembic upgrade head
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/manashelper
env DATASOURCE_HOST=localhost \
  ADVERTISEMENT_CHANNEL_ID=-1000000000000 ADVERTISEMENT_CHANNEL_LINK=https://t.me/example \
  MODERATION_CHAT_ID=-1000000000001 ADMIN_CHAT_ID=-1000000000002 \
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
