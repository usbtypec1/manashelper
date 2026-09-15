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
- **Scheduled notifications** (`scheduler_jobs.py`, wired up in `main.py`): the daily menu is broadcast to
  opted-in users at 11:00/17:00 Bishkek time; OBIS exam grades and lesson attendance are polled hourly per user
  and diffed against previously-seen state to notify only on actual changes; each tracked course's timetable is
  scraped hourly and diffed to notify trackers of schedule changes — see "Scheduled jobs & change detection"
  below.
- **Localization**: every user-facing string is served through aiogram's built-in gettext-based i18n, with the
  user's locale auto-detected from Telegram, falling back to a language picker — see "Localization (i18n)" below.
- `/start` resolves the user's locale, upserts the Telegram user, and shows the main reply keyboard.

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
`python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"`), and optionally
`DATASOURCE_HOST` (defaults to `db`, the docker-compose service name — set to `localhost` for local dev outside
Docker). `docker-compose.dev.yml` starts only Postgres, exposed on host port `5432`. A local `.env` file
(gitignored) is read automatically via `pydantic-settings`.

Deployment: pushing a `v*` tag triggers `.github/workflows/ci-cd.yml`, which first runs lint + type-check + tests
against a Postgres service container, then — only if that passes — builds the Docker image
(`docker/Dockerfile`) and pushes `usbtypec1/manashelper:<version>` / `:latest` to Docker Hub, then SSHes into the
deploy host to pull and restart via `docker compose up -d`.

## Architecture

### Package layout (by layer, not by feature)

Under `src/manashelper/`, code is organized by technical layer, mirroring the original Java structure:
`bot/routers` (aiogram handlers), `bot/keyboards` (inline keyboard builders), `bot/middlewares`, `bot/callback_data.py`,
`services` (business logic), `repositories` (SQLAlchemy queries), `db/models` (ORM models), `config.py`, `di.py`,
`main.py`. As with the Java version, expect this to stay flat-by-layer rather than gaining per-feature
subpackages as more of the roadmap gets ported.

**Services return plain dataclasses, never ORM models.** A `service` method called from a `bot/routers` handler
returns a frozen `dataclass` (e.g. `FacultyModel`, `DepartmentSummary`, `CourseSummary`) or raises, never a
SQLAlchemy model instance — routers must never hold an ORM object. Map ORM model → dataclass with a private
module-level helper next to the service class (see `course._to_summaries`, used by `CourseService`).

**`services/` classes exist to hold DI-injected collaborators, not as Java-style ceremony.** A `*Service` class's
`__init__` takes the repositories (and other collaborators, e.g. `CryptoService`, `ObisClient`) it needs and
stores them as attributes; its methods are the only thing a router or `scheduler_jobs.py` depends on via
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
`message.from_user.language_code`, otherwise returns `None`. A `None` result shows a 4-language picker
(`bot/keyboards/locale.py`) and stops propagation *except* for a tap on that very picker (a `LocaleCallback`,
detected by its packed prefix) — that one is let through unconditionally, or a user who can't be auto-detected
could never get past the picker. On success, the middleware enters `i18n.context()` / `i18n.use_locale(...)` and
calls the handler inside it, so every `_()`/`ngettext()` call made anywhere during that update — filters,
handlers, keyboards, formatters — resolves against the right locale via the contextvar aiogram's `I18n` keeps,
with no `Translator`/locale parameter threaded through call signatures. `bot/filters/translated_text.py`
(`TranslatedText`) exists because a reply-keyboard button's label is only known once translated, so matching the
incoming message text against a hardcoded string (`F.text == "..."`) can't work across locales.

`scheduler_jobs.py` runs outside any Telegram update, so there's no ambient middleware to set the gettext context;
each per-recipient send there looks up that user's `Locale` and wraps its own `format_...(...)` call in
`with i18n.context(), i18n.use_locale(locale.value): ...` explicitly. A user can change their locale later via
`/language` or the "🌐 Language" row in Settings (`bot/routers/locale.py`), which reuses the same picker.

### Scheduled jobs & change detection

`scheduler_jobs.py` holds every `AsyncIOScheduler` job function registered in `main.py::main`; each job opens its
own short-lived Dishka request scope(s) (`async with container() as request_container`) rather than reusing one
across the whole run, and wraps its body in a broad `except Exception: logger.exception(...)` so one failure
(a bad HTML page, a dead OBIS login, a user who blocked the bot) never aborts the rest of the batch — the same
resilience shape as the pre-existing `sync_daily_menus_job`. Per-recipient Telegram sends are wrapped individually
in `except TelegramAPIError` for the same reason.

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
- **Daily menu broadcast** (`scheduler_jobs.py::broadcast_lunch_menu_job`/`broadcast_dinner_menu_job`, cron
  11:00/17:00 `Asia/Bishkek`): re-sends the same media-group format used for an on-demand `/yemek` request to
  every user with `before_lunch_enabled`/`before_dinner_enabled`.

`NotificationSettingsRepository` centralizes "who should be notified": a user with no `NotificationSettings` row
yet (never opened the settings menu) counts as every toggle being enabled — the repository queries use
`LEFT JOIN ... WHERE column IS DISTINCT FROM FALSE`, not `= TRUE`, specifically so an absent row doesn't silently
opt a user out.

## Roadmap (not yet ported from the Java version)

- **About screens**: static informational callback handlers.
