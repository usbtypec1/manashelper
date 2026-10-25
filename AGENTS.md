# AGENTS.md

Guidance for Codex in this repository. This is the working reference for the current Python bot. `CLAUDE.md`
contains more feature history and implementation rationale; check the code when the two documents differ.

## Project

Manashelper is a Python 3.13 Telegram bot for Manas University students. It uses aiogram 3, async SQLAlchemy 2,
Postgres, Dishka dependency injection, Alembic, APScheduler and gettext. There is no REST API. The entry point is
`src/manashelper/main.py`; users interact with the bot through Telegram long polling.

Current features include the faculty/department/course catalog and course tracking, timetable and lesson search,
cafeteria menus, OBIS grades and attendance, notification settings, scheduled change notifications, advertisements
with moderation and a channel, feedback and admin broadcasts, and `/donate` with bank QR codes. Read the relevant
router, service, repository, and tests before changing a feature. `features/` holds some feature specifications.

## Architecture

Code is organized by layer under `src/manashelper/`: `bot/routers` (handlers), `bot/keyboards`, `bot/middlewares`,
`bot/callback_data.py`, `services`, `repositories`, `db/models`, `scraping`, `jobs`, `localization`, `config.py`,
`di.py`, and `main.py`. A gradual feature-first migration is in progress: feedback, advertisements and the survey live in
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
its Telegram sender preserves per-recipient locale and delivery behavior. StudyWeekService remains a legacy consumer.
`modules/notifications/` is partial: only the recipient query and REQUEST provider have moved; settings/ORM/repository remain legacy.
Shared weekday labels live in `localization/weekdays.py`; reuse `services/time_utils.py::BISHKEK_TZ` instead of a feature's timezone.
`modules/users/` currently exposes UsersQuery and a REQUEST provider for counts, recipient IDs and existence
checks used by donations, broadcasts and Food menu. Other user functionality, ORM and repository remain legacy.
Keep migrated feature code together;
do not move unrelated legacy areas in the same stage. See `docs/ARCHITECTURE.md` and `docs/MIGRATION.md`.
Add routers to the dispatcher in `bot/dispatcher.py`; legacy services/repositories remain in `di.py`, while migrated
features own their providers. Router order matters because aiogram uses the first matching handler; the
advertisement deep-link router must precede the plain `/start` router. Use typed `CallbackData` classes for inline
button payloads.

Routers and jobs depend on services, not repositories or `AsyncSession`. Services hold injected collaborators and
business logic; repositories handle persistence. Services return plain dataclasses, not ORM instances, to the
presentation layer. Put pure mapping and formatting helpers at module level. Escape user-provided and other dynamic
text with `services/html_sanitization.py::escape_html` before inserting it into Telegram HTML messages.

`di.py` has an application scope for settings, engine, session factory, clients and shared services, and a request
scope for sessions, repositories and most services. The session commits on normal finalization and rolls back if
commit raises. An existing defect is characterized in `tests/test_feedback_composition.py`: Dishka sends a request-body
exception as the yield value, which the provider ignores, so a body exception alone still leads to commit. Do not
silently fix this while relocating a feature. New handlers use `FromDishka[...]`; jobs open request scopes with
`async with container() as request_container`. Keep `setup_dishka(container, dispatcher)` followed by an explicit
`inject_router(dispatcher)`; `auto_inject=True` conflicts with aiogram startup callbacks in the current versions.

`PerChatOrderingMiddleware` serializes updates from one chat, which protects flows that read and then change user
state. `RateLimitMiddleware` runs before it. `LocaleMiddleware` runs after Dishka setup so it can use the request
container. Keep middleware registration order and router filters in mind when adding handlers.

Schema changes go through legacy `db/models` or the owning feature's ORM and an Alembic migration in `alembic/versions`.
The global model registry still imports migrated models for Alembic. File relocation alone needs no schema migration.
Generate migrations with
`uv run alembic revision --autogenerate -m "description"` when a database is available, then review the generated
operations. `main.py` applies migrations on startup; `uv run alembic upgrade head` applies them manually.

## Feature-specific conventions

- Food menu keeps rich/ephemeral message behavior, fixed-date callbacks, per-chat cleanup and weekday meal
  notification settings. A characterized existing defect makes the first lunch toggle on an absent settings
  row remain enabled until another toggle; do not silently fix ORM-default timing during relocation.

- OBIS credentials are verified with a real login before storage and encrypted with AES-GCM through
  `CryptoService`. The credentials form uses aiogram FSM and in-process `MemoryStorage`. OBIS fetches authenticate
  per call; do not assume a persistent browser session.
- Notification jobs live in `jobs/` and are registered in `jobs/scheduler.py`. They use independent request scopes, catch
  failures per item or recipient, and log unexpected exceptions so one failure does not stop a batch. Grade,
  attendance and timetable notifications compare a new snapshot with persisted last-known state and do not notify
  on the first observation. Users without a `NotificationSettings` row have all toggles enabled.
  Migrated Food menu and Schedule jobs live in their modules. Schedule loads course IDs in one request scope,
  then opens another per course. TelegramAPIError skips a recipient; unexpected delivery/locale errors abort
  that course, are logged, and do not prevent the next course. Keep this boundary and the hourly schedule.
- Marketplace moderation is authorized by `Settings.moderation_chat_id`, not a user role. Approved ads go to the
  configured channel. Public posts hide contact details behind a `/start ad_<id>` link; contact opens are logged.
  The channel post IDs must remain available for deletion when an ad is removed or expires. The marketplace menu
  is a reply keyboard reached from its main-menu button or `/start market`.
  Expiry runs through `modules/advertisements/jobs.py` and `ExpireAdvertisements`; the use case depends on its
  repository and `PublicationRemover`, while the Telegram adapter handles batching and best-effort failures.
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
`bot/filters/translated_text.py::TranslatedText` for reply-keyboard text filters rather than matching one
language's label directly.

`LocaleMiddleware` chooses a user's saved or Telegram-detected locale and falls back to Russian. Code sending a
message to another user must format it inside that recipient's `i18n.use_locale(...)` context; jobs must also
establish `i18n.context()` because they run outside update middleware. Shared moderation/admin chats and the
advertisement channel render in `DEFAULT_LOCALE`.

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
Check command definitions in `services/bot_commands.py` and registration in `bot/commands.py` as well as the handler.

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

The app needs Postgres and the environment variables defined in `src/manashelper/config.py`: Telegram token,
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
