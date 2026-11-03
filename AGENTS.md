# AGENTS.md

Shared repository instructions for coding agents. Keep instructions here; `CLAUDE.md` imports this file for Claude Code.
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for implementation details and rationale,
and [docs/BACKLOG.md](docs/BACKLOG.md) for deferred work. Check the code when documentation differs.

## Project

Manashelper is a Python 3.13 Telegram bot for Manas University students. It uses aiogram 3, async SQLAlchemy 2,
Postgres, Dishka dependency injection, Alembic, APScheduler and gettext. The bot entry point is
`src/manashelper/main.py`; one aiohttp process owns the Telegram webhook, optional private administration API,
built Mini App assets and scheduler. Production defaults to webhook; development polling must be selected explicitly.
Never register/delete a Telegram webhook or discard pending updates on startup.

Current features include the faculty/department/course catalog and course tracking, timetable and lesson search,
cafeteria menus, OBIS grades and attendance, notification settings, scheduled change notifications, advertisements
with moderation and a channel, feedback and admin broadcasts. Read the relevant
router, service, repository, and tests before changing a feature. `features/` holds some feature specifications.

## Architecture

The reusable UI-flow engine lives in `src/ui_flows/` (domain/application/ports),
without dependencies on manashelper, Telegram, aiohttp, ORM or DI. Shared SQLAlchemy Base
lives in `src/common/database.py`. Application adapters, rollout, seed documents and DI
remain in `src/manashelper/modules/ui_flows/`; survey delegates belong to student_questions.
Persistence ports are aliases to the same REQUEST repositories; preserve their transaction
with business delegates. See `features/UI_FLOW_EDITOR_PLAN.md`,
`features/ui_flows/CONTRACT.md`, `features/ui_flows/RUNTIME.md`, `features/ui_flows/TELEGRAM.md`
and `features/ui_flows/ADMIN_API.md`.
The agreed next-stage plan is `features/ui_flows/ORCHESTRATION.md`: move all UI
decisions and event routing into the engine, compose small typed scenarios with Python
delegates, migrate every FSM form/cache, and finally use Dispatcher(disable_fsm=True).
Stages 1–4 provide the checked UI inventory, shared aiohttp host, admin-only Mini App,
versioned DB localization and unified ingress/trigger registry. Stages 5–6 add v2
Call/Return/Replace with pinned dependencies and durable isolated frames, typed collections,
saved action snapshots, contact/media/secret input, external operations and rich delivery.
Feature cutover and complete FSM removal remain stages 7–12. See PROGRESS.md for checks.
External operations commit unknown before I/O and never automatically retry an unknown
attempt. Completion must use the APP ChatOrdering shared with both message and callback
middleware, covering apply through screen delivery without keeping a REQUEST open while
waiting for the gate. Keep external execution outside both the DB lock and ordering gate.
Preserve existing feature behavior until each migration stage has its compatibility checks.
See `features/ui_flows/TRIGGERS.md`: the Telegram adapter normalizes events and the pure resolver chooses
one runtime or registered legacy owner. Trigger publications pin scenario/text versions and return targets;
publish texts, then a fresh scenario revision, then a fresh Triggers revision to adopt changes.
Keep compatibility bindings immutable, admin/moderation/capability guards and busy-dialog policies.
Only the legacy OBIS password field treats unknown/inaccessible slash commands as opaque masked input.
Ingress receipts persist route metadata and source session/revision, never input/FSM payloads.
Skip completed runtime replays before handler side effects; pending replays require their original position
and current launch access. Keep legacy I/O outside DB chat locks and runtime execution after REQUEST commit.
The nullable trigger pin preserves old writers. Roll back by activating a compatible immutable manifest,
not by removing receipt history. Call/Return frames and durable legacy forms belong to later stages.
The interpreter, persistence and REQUEST provider are composed in main. Telegram's
`/flow_demo` is a private admin-only pilot. Main/Studies menus now use a published `main_menu` flow for the
private administrator by default. Release mode admin/all/off is persisted in ui_flow_rollout and managed in the
editor; all enables public menu/survey entry, off denies new launches while active sessions continue.
The survey deep link resumes an active runtime even when new launches are off; existing legacy surveys keep their owner.
The administrative HTTP API and Vue editor (`src/admin-ui/`) are implemented. The eight owned tables are registered
explicitly in bootstrap. Keep publication versions
immutable, pin active sessions to their version, and serialize first launches with the
transaction-scoped chat lock plus the partial unique active-session index. Delegate DB
writes, state and event deduplication share one transaction; repository savepoints also
roll back failed operations when an outer caller catches the error. Only transactional
delegates are supported so far; do not run network calls while holding a chat lock.
Runtime handlers enqueue work in AfterRequestActions. Keep AfterRequestMiddleware inside
PerChatOrderingMiddleware and outside Dishka, so the profile/audit scope commits before
the APP coordinator opens its own REQUEST. Never execute the coordinator from inside the
update's original REQUEST: profile upserts can hold locks required by the new scope.
State, event and screen intent commit together; claim persists unknown before Telegram I/O.
Unknown attempts are never automatically resent; `/flow_demo` explicitly restores the step.
Use saved displayed labels for reply actions and opaque delivery tokens for typed callbacks.
Inline screens use a text message with ReplyKeyboardRemove, followed by a separate localized message with
InlineKeyboardMarkup. Persist the second message ID. Telegram cannot edit a ReplyKeyboardRemove message;
never attach inline buttons to it using editMessageReplyMarkup. The mock enforces this live-verified restriction.
Mask runtime input in action_logs. Locale/theme selection preserves the runtime session;
other matched legacy navigation cancels it after the original request commits.
Web authentication lives in `platform/web/`, with two separately owned tables registered in bootstrap.
Private admin-only `/editor` opens a Web App button and retains a five-minute, single-use browser ticket
after the update REQUEST commits. Mini App auth verifies signed initData, administrator ID and a five-minute age;
its eight-hour bearer lives only in browser memory. The single host limits valid exchanges to five per minute.
Bearer session digests use the miniapp: namespace; token grammar prevents cookie/bearer namespace conversion.
The login page removes its fragment before exchanging it for an eight-hour Secure/HttpOnly/SameSite=Strict cookie.
Persist only token digests. Check configured HTTPS Origin on all browser mutations, including bearer requests;
require CSRF for cookie mutations.
The aiohttp admin_scope middleware completes its REQUEST scope before returning any response, including login cookies;
errors must escape
the scope before being mapped to HTTP status codes. Preview builds a new registry from definitions and explicit stubs;
never execute live delegate handlers there. Monitoring returns runtime metadata without session answers or screen text;
legacy observation records only handler/state names after a successful committed private-chat handler.
The shared process requires the optional admin web origin and signing key when web access is enabled.
The HTTP-only test factory does not apply migrations or start a bot/scheduler; main applies migrations as before.
Webhook uses Dispatcher.feed_update synchronously with webhook=True; on_error must rethrow so commit failures
cannot become HTTP 200. Accept only message/callback_query updates with the configured secret and a 1 MiB limit.
Cap webhook concurrency at 32 and preview concurrency at four; unknown delivery attempts remain unresent.
Legacy handlers still lack universal durable update receipts; do not claim global exactly-once legacy delivery.
The editor uses Vue 3, TypeScript and Vue Flow; use Bun for dependency management AND JavaScript execution,
never npm or Node.js. Commit `src/admin-ui/bun.lock`, not package-lock.json. Run `bun run build`, `bun run test`,
`bun run format:check` and `bun run test:e2e` in src/admin-ui. E2E builds first, runs Playwright through Bun and
a real loopback HTTPS aiohttp fixture with its own development PostgreSQL schema; no live Telegram is used.
UI-flow session fixtures use isolated schemas too, preserving authored documents and observations in the development DB.
The HTTP process serves only built index/assets from src/admin-ui/dist. Preserve script CSP, cookie/CSRF checks,
fragment removal and memory-only credentials. Preview renders supported Telegram tags through Vue VNodes,
never v-html or executable HTML. Graph edges map to explicit transition ports; coordinates belong only to layout.
Keep generated API types in sync via `bun run generate`. The administration UI is English-only, including its
fallback login page; editor system copy stays in the English gettext catalog. User-facing bot content, inline
text variants and preview keep all five languages. Do not reintroduce an administration language selector.
literal calls live in presentation/editor_copy.py. Compile catalogs, then run
`python scripts/export_ui_flow_editor_copy.py` (or `--check`) for the browser bundle.
Private admin-only `/flow_demo <id>` opens any published pilot scenario; a different active dialog must finish
or be cancelled first. Empty arguments preserve the original seeded demo.
Bot startup marks legacy positions unknown because MemoryStorage is lost, then seeds/publishes `main_menu` only
if it is absent. Never overwrite an existing draft or publication. Runtime positions remain resumable.
The same bootstrap seeds `student_questions` only after its root return flow is published. The initial document
lives in the owning survey module; DB versions remain authoritative after creation. Preserve explicit replacement
confirmation and save only through StudentQuestionsService at completion. Legacy survey callbacks preserve an
unrelated runtime session when rejecting expired buttons. Keep the survey deep-link router before legacy/deep links.
Telegram calls DialogService with follow_returns=True: terminal state, DB delegate, new pinned menu session,
event and screen intent share one transaction. A return target must start at Menu/Input, preventing automatic
cross-flow cycles. UiFlowEvent keeps the source session and optional result_session_id so repeated final events
return the same target session without another write. Never copy form data into a return session or metadata.
Migration 41edcfaadf86 adds that nullable FK; old rows/writers remain compatible. See features/ui_flows/SURVEY.md.
Rollout changes use expected_revision and a short shared row lock during launch/return admission. Keep active input,
reply and callback handlers independent of rollout mode; /editor and /flow_demo remain admin-only.
Off/admin rollback suppresses a public form's automatic return session and sends its legacy menu instead.
Cleanup runs at 04:15 Bishkek: clear closed payloads and remove their screens after seven days, retaining active state,
business answers, metadata and event receipts. Auth cleanup runs at 04:20 and deletes only expired tickets/sessions.
Docker builds frontend through Bun and includes dist in the Python runtime; the app service publishes one
loopback HTTP port. FastAPI/Uvicorn and the separate admin service/entry point are removed. Scheduler shutdown
awaits coroutine finalizers before closing DI, HTTP clients and DB resources.
See features/ui_flows/RELEASE.md for rollout, retention and rollback.
Current reply buttons precede global navigation; the admin menu router accepts only bare /start, preserving
survey/ad payloads. Explicit root navigation cancels the old dialog and starts the current menu version atomically.
`navigation_entries.study` references a Menu node and follows node renames. Existing features are entered through
their shared public presentation entry points, never by calling handlers or synthesizing updates.
Commit the terminal state/intent and claim before running a feature; pass the actual user ID even for callbacks
whose message author is the bot. Keep Eders/Study week availability checks in the adapter as well as button guards.
Runtime state/event/location/history share one transaction. UiFlowObservationMiddleware follows privacy/navigation
guards and queues metadata after the original request commits. Skip active runtime and runtime-flagged handlers.
Do not compare update IDs numerically to order locations: Telegram may randomize them after an idle week.
Use chat ordering and receipts; history has its own keyset ID. Never copy FSM data into monitoring tables.
The Users screen polls every five seconds while visible and reads immutable versions through the admin API;
it must not mutate the draft, session or user position. Unobserved users and lost legacy state remain unknown.
See `features/ui_flows/MONITORING.md` for menu adapters, projection semantics and migration/backfill.
Generate `features/ui_flows/{flow.schema.json,openapi.json}` with
`python scripts/export_ui_flow_contracts.py`; use `--check` to detect stale artifacts.
Scenario-authored `InlineText` stays inside immutable flow documents with locale/theme variants.
`CatalogText`, user-facing errors, commands and notifications read versioned DB text releases.
`platform/i18n/` owns two tables, the import, repository, REQUEST service and adapter;
`ui_flows` owns the transport-independent TextCatalog port, snapshot and validation.
Migration d91e6b1a7f23 imports baseline 1 and pins existing flow versions without changing
their documents/answers. Nullable pins from old writers resolve to baseline 1. Never update/delete
published releases; activate a previous release to roll back. Flow publications pin the current
REQUEST snapshot; save a new draft revision (even with the same graph), then publish to adopt new texts.
Keep retries of an already published revision idempotent, including after rollback. Existing sessions and historical
preview/monitoring keep their pin. Delivery intents carry their pin through post-commit I/O.
Bind a DB snapshot explicitly in LocaleMiddleware, catalog_request jobs/coordinators and admin scopes;
never add a user-facing .mo fallback. REQUEST caches must not leak uncommitted publications.
Historical legacy reply labels remain valid; reject publication of ambiguous current/history labels.
See features/ui_flows/LOCALIZATION.md. The administration interface remains English-only.

Business features live in `modules/`; shared infrastructure lives in `core/` and `platform/`.
The planned feature migration is complete. `bootstrap.py` explicitly loads ORM models; `jobs` keeps scheduler wiring,
and `core/time.py` owns the shared timezone. Schedule owns its application text normalization helper.
Empty legacy `bot/`, `services/`, `repositories/` and `scraping/` packages were removed. Feedback, advertisements and the survey live in
`modules/feedback/`, `modules/advertisements/` and `modules/student_questions/`, with REQUEST providers in `main.py`.
Advertisements separates presentation, application and infrastructure, with domain enums; feedback and the survey stay flat.
Broadcast lives in flat `modules/broadcast/`: SendBroadcast uses active IDs from UsersQuery and a delivery protocol;
Telegram localization, HTML, one-photo delivery and API errors stay in its sender adapter. Its provider retains REQUEST scope.
Broadcast accepts a text/photo draft and URL or existing callback buttons, with preview and explicit confirmation.
User.bot_stopped is the shared persistent delivery flag. Recipient SQL and UserMessageDelivery suppress stopped users
across broadcasts, Food menu, Schedule, OBIS and Eders; permanent recipient errors set it in the same request scope.
A private-chat profile refresh clears it; group activity preserves it. Notification preferences and snapshot syncs stay intact.
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
EdersService reads the student number without decrypting a password for direct login and cached snapshots.
Only a failed direct login triggers OBIS credential decryption and the legacy OBIS SSO fallback.
Eders tracking checks existence through UsersQuery; its repository owns credential eligibility SQL and the user-row lock.
Shared Telegram navigation lives in `platform/telegram/navigation.py`; feature routers must not import the start router for it.
The main keyboard groups academic features under Studies. Its reply submenu reuses existing feature labels and hides
Eders/Study week when disabled. The platform navigation router handles Studies and Back before feature FSM handlers,
clearing unfinished forms on navigation; the shared Back handler also serves Marketplace.
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
StudyWeekProvider owns its REQUEST use case. Keep the single Base from `common/database.py`.
The `db` package was removed. Import ORM classes from their owning feature/platform modules, never from a global facade.
Call `bootstrap.load_models()` at application/test/Alembic bootstrap before using ORM. It registers all model modules and
configures string relationships without re-exporting classes. Standalone compositions must call it explicitly;
importing one repository no longer loads the whole schema as a side effect.
Telegram Platform lives in `platform/telegram/`: dispatcher, commands/catalog/extractor, navigation,
Settings callbacks/routers, filters, middleware, HTML/delivery, audit and scheduled message deletions.
TelegramPlatformProvider owns both audit and deletion repositories/services in REQUEST. Audit records only
matched/allowed updates from private chats only, masks password text with `[masked]`, and stays after the private-chat guard.
Cleanup jobs use MessageDeletionService.delete_due with async delivery; delete_messages batches by 100,
continues after TelegramAPIError and propagates unexpected errors. Rows are acknowledged after all chats;
an unexpected sweep failure logs and leaves them queued. Preserve the five-minute schedule and no retry.
The gettext-compatible DB adapter lives in `platform/i18n/catalog.py`; locale/weekday helpers stay in `localization/`.
Command JSON and English administration .mo paths are unchanged, with checkout/Docker-like path tests.
OBIS lives in `modules/obis/`: application facade/credentials/snapshot comparison/polling, HTTP/parser/crypto,
credential and snapshot repositories/ORM, Telegram presentation, provider and jobs. ObisProvider keeps
ObisClient/CryptoService in APP and all other dependencies in REQUEST. Public errors live in errors.py.
ObisService retains save/has/clear/get methods; ObisCredentialsService owns verification/storage/decryption.
Its frozen read model hides secrets in repr; OBIS credentials retain the SHA-256 ciphertext marker.
Eders owns its HTTP client: try direct Moodle form login first, then the legacy OBIS login and /site/eders SSO flow.
PollObisUser handles expected auth/parse errors; Telegram sender owns locale/HTML and skips TelegramAPIError.
Unexpected errors abort that user and are logged by the job, without stopping the next user.
The first grade snapshot and attendance's first row are silent. Later new or changed nonempty grades notify.
Saving verifies login and encrypts the password before assigning either credential field, so login/encryption failures
preserve both previous values even if caught inside a committed scope. Preserve 15-minute polling, FSM,
password masking and encryption format.

OBIS and Eders user screens read persisted snapshots only, including Study week. Background jobs refresh both
every 15 minutes (Eders retains its existing interval override). Notification toggles affect delivery, not
synchronization. Missing snapshots show a preparation message; failed refreshes preserve the last successful data.
Snapshot reads must not acquire locks held during HTTP fetches. OBIS credential changes clear cached results
and comparison baselines; Eders validates its student-number marker.

Eders lives in `modules/eders/`: application snapshot/filter/tracking/polling, infrastructure client/parser/URL validation,
serialization/repository/ORM, Telegram presentation, jobs and provider. EdersProvider keeps the client APP and other
dependencies REQUEST. PollEdersUser preserves refresh→locale→pending→send→ack ordering; its Telegram sender groups
materials and yields delivered events for immediate acknowledgement. TelegramAPIError skips one message without ack;
unexpected errors abort only that user. Preserve snapshot JSON, event keys, baseline/account/schema suppression,
monotonic observations, user-row FOR UPDATE before first state, and the one-retry whole-snapshot login flow.
The optional MANASHELPER_EDERS_PASSWORD env value is the shared Moodle password; obtain logintoken from the form for every login
and detect successful login by an authenticated page with sesskey, without a redirect URL allowlist.
Missing or empty MANASHELPER_EDERS_PASSWORD disables Eders and Study week routers,
main-menu buttons, Eders notification settings and polling. Legacy commands remain hidden aliases when enabled.
Eders polling requires only a nonempty saved student number; the snapshot marker is SHA-256 of that number.
The first sync after switching from the ciphertext marker establishes a silent account baseline.
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
  Attendance/timetable first observations and the first OBIS grade snapshot are silent.
  Users without a `NotificationSettings` row have all toggles enabled.
  Food menu, Schedule, OBIS and Eders jobs live in their modules. Schedule loads course IDs in one request scope,
  then opens another per course. TelegramAPIError skips a recipient; unexpected delivery/locale errors abort
  that course, are logged, and do not prevent the next course. Keep this boundary and the hourly Schedule job.
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
  Telegram's native reply action. `/broadcast` is registered only for that chat and sends to active registered users.
  Broadcast clears FSM before loading recipients and sends sequentially without retry. TelegramAPIError during
  delivery skips that recipient; locale lookup failures and unexpected errors abort without a summary.

## Localization and Telegram text

Use stable message keys with literal `_("menu.settings")` or `ngettext(...)` arguments.
User templates live in versioned DB releases for English, Russian, Kyrgyz, Turkish and Chinese (`zh`).
Edit existing translations through Texts, save with expected_revision, then publish explicitly.
Key/owner/parameter/content/plural contracts are immutable. New keys require an explicit reviewed catalog
migration preserving operator edits; startup/import must never overwrite an existing draft or release.
The five `.po` catalogs remain baseline/recovery material; ui_flows.editor.* and ui_flows.web.* are
English-only administration copy. Dynamic strings and f-strings are not extractable by Babel.
English remains the locale fallback. Preserve formatting placeholders in every translation. Use
`platform/telegram/filters/translated_text.py::TranslatedText` for reply-keyboard text filters rather than matching one
language's label directly.

`LocaleMiddleware` chooses a user's saved or Telegram-detected locale and falls back to Russian. Code sending a
message to another user must format it inside that recipient's `i18n.use_locale(...)` context; jobs must also
establish `i18n.context()` because they run outside update middleware. Shared moderation/admin chats and the
advertisement channel render in `DEFAULT_LOCALE`.
Evaluate translation calls and message builders inside the recipient's locale context; wrapping an already-built
string cannot change its language. Personal notifications also bind the recipient's saved Theme through i18n.use_theme;
never inherit another recipient's theme. Basic is the default. Imported theme variants are already
materialized in DB; never decorate them again. Interpolate escaped user content after selecting the variant;
preserve dishes, photos, numbers, callback payloads and status meanings.

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

Use `uv` 0.8.17+ for dependency management (the build contains three Python modules).
From the repository root:

```sh
uv sync
uv run alembic upgrade head
uv run python -m manashelper.main
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/manashelper src/ui_flows src/common
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
.venv/bin/mypy src/manashelper src/ui_flows src/common
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
