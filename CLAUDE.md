# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Manashelper is a Telegram bot (Python 3.13, aiogram 3, SQLAlchemy 2 async, Dishka DI) for Manas University
students. There is **no REST API** — all user interaction happens through Telegram long-polling.

This is a from-scratch Python rewrite of a former Java/Spring Boot implementation. As of this rewrite, only one
vertical slice is implemented: **timetable browsing** — faculty → department → course listing with per-user
course tracking. OBIS integration, the cafeteria daily menu, lesson-change notifications, and the "About" screens
from the original Java bot have not been ported yet (see Roadmap below).

Core capabilities (current):

- **Faculty/department/course catalog browsing** via inline keyboards, backed by Postgres.
- **Per-user course tracking**: tapping a course toggles tracking it (✅) via a `user_courses` join table.
- `/start` upserts the Telegram user and shows the main reply keyboard.

## Commands

Dependency management is via `uv`. Run from the repo root:

```
uv sync                                                # install dependencies + create .venv
uv run alembic upgrade head                            # apply migrations (also runs automatically on app boot)
uv run alembic revision --autogenerate -m "message"    # generate a new migration from model changes
uv run python -m manashelper.main                      # run the bot locally (needs env vars below + Postgres)
uv run pytest                                          # run tests (needs the dev Postgres running)
uv run ruff check .                                    # lint
uv run ruff format .                                   # format
uv run mypy src/manashelper                            # type check
```

Checkstyle-equivalent strictness: `ruff` enforces a 120-char line length, import ordering, no unused/wildcard
imports, PEP8 naming, and pyupgrade rules (`pyproject.toml` → `[tool.ruff]`). `mypy --strict` runs over
`src/manashelper` (not `tests/` or `alembic/versions/`, which are excluded from strict typing/line-length rules
respectively — see `pyproject.toml`/`[tool.ruff] extend-exclude`).

### Running locally

The app needs Postgres and these environment variables (see `src/manashelper/config.py`): `TELEGRAM_BOT_TOKEN`,
`DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD`, and optionally `DATASOURCE_HOST` (defaults to
`db`, the docker-compose service name — set to `localhost` for local dev outside Docker). `docker-compose.dev.yml`
starts only Postgres, exposed on host port `5432`. A local `.env` file (gitignored) is read automatically via
`pydantic-settings`.

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
SQLAlchemy model instance — routers must never hold an ORM object. Map ORM model → dataclass at the bottom of the
service method (see `CourseService._to_summaries`).

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

## Roadmap (not yet ported from the Java version)

- **Lesson scraping/sync**: a `Lesson` model, timetable HTML scraping (`httpx` + an HTML parser) against
  `http://timetable.manas.edu.kg/department-printer/{course_id}`, a change-detection + sync pipeline, an
  APScheduler-driven hourly job — and, since the Java version never finished this, actually notifying users who
  track a course when its lessons change.
- **OBIS integration**: student-portal login (cookie-based session per chat), attendance/exam-grade fetching and
  parsing, encrypted credential storage (the Java version used raw AES-ECB — a Python rewrite should use AES-GCM
  instead, which is a breaking change for any already-encrypted data and needs an explicit migration decision),
  and a multi-step credential-entry conversation flow (aiogram FSM — e.g. `RedisStorage` for multi-worker
  deployments — as the closest analog to the Java project's separate `telegram-fsm-core` library).
- **Cafeteria daily menu**: menu scraping, dish ratings, the 10-minute sync job.
- **About screens**: static informational callback handlers.
