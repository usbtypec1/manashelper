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
`di.py`, and `main.py`. Keep that layer-based structure. Add routers to the dispatcher in `bot/dispatcher.py` and register
services/repositories in `di.py`. Router order matters because aiogram uses the first matching handler; the
advertisement deep-link router must precede the plain `/start` router. Use typed `CallbackData` classes for inline
button payloads.

Routers and jobs depend on services, not repositories or `AsyncSession`. Services hold injected collaborators and
business logic; repositories handle persistence. Services return plain dataclasses, not ORM instances, to the
presentation layer. Put pure mapping and formatting helpers at module level. Escape user-provided and other dynamic
text with `services/html_sanitization.py::escape_html` before inserting it into Telegram HTML messages.

`di.py` has an application scope for settings, engine, session factory, clients and shared services, and a request
scope for sessions, repositories and most services. A request-scoped session commits when its scope succeeds and
rolls back on exception. New handlers use `FromDishka[...]`; jobs open their own short-lived request scopes with
`async with container() as request_container`. Keep `setup_dishka(container, dispatcher)` followed by an explicit
`inject_router(dispatcher)`; `auto_inject=True` conflicts with aiogram startup callbacks in the current versions.

`PerChatOrderingMiddleware` serializes updates from one chat, which protects flows that read and then change user
state. `RateLimitMiddleware` runs before it. `LocaleMiddleware` runs after Dishka setup so it can use the request
container. Keep middleware registration order and router filters in mind when adding handlers.

Schema changes go through `db/models` and an Alembic migration in `alembic/versions`. Generate migrations with
`uv run alembic revision --autogenerate -m "description"` when a database is available, then review the generated
operations. `main.py` applies migrations on startup; `uv run alembic upgrade head` applies them manually.

## Feature-specific conventions

- OBIS credentials are verified with a real login before storage and encrypted with AES-GCM through
  `CryptoService`. The credentials form uses aiogram FSM and in-process `MemoryStorage`. OBIS fetches authenticate
  per call; do not assume a persistent browser session.
- Notification jobs live in `jobs/` and are registered in `jobs/scheduler.py`. They use independent request scopes, catch
  failures per item or recipient, and log unexpected exceptions so one failure does not stop a batch. Grade,
  attendance and timetable notifications compare a new snapshot with persisted last-known state and do not notify
  on the first observation. Users without a `NotificationSettings` row have all toggles enabled.
- Marketplace moderation is authorized by `Settings.moderation_chat_id`, not a user role. Approved ads go to the
  configured channel. Public posts hide contact details behind a `/start ad_<id>` link; contact opens are logged.
  The channel post IDs must remain available for deletion when an ad is removed or expires. The marketplace menu
  is a reply keyboard reached from its main-menu button or `/start market`.
- Feedback and `/broadcast` are restricted to `Settings.admin_chat_id`. Admins reply to forwarded feedback using
  Telegram's native reply action. `/broadcast` is registered only for that chat and sends to all registered users.
- `docs/requisites/` holds `/donate` bank QR images. Filenames provide bank labels. `DonationQrService` reuses
  Telegram file IDs with bounded LRU caching. If runtime data is added under `docs/`, copy its directory in
  `docker/Dockerfile`.

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

## IDE integration

Use the `jetbrains-index` MCP server when available for semantic code operations: `ide_find_references` for usages,
`ide_find_definition` for navigation, `ide_refactor_rename` for project-wide renames, `ide_type_hierarchy` and
`ide_find_implementations` for relationships, and `ide_diagnostics` for inspections. The IDE's semantic index is
preferable to text search for code symbols; use `rg` when the server is unavailable or for plain text searches.
