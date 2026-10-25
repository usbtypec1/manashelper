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
- **Cafeteria daily menu**: a rich message with dish photos in a compact collage, a dish/calorie list and one 1–5 rating row for the
  whole day's menu. Ratings are unique per menu and user; voting again updates the score and refreshes the message.
  Notification settings appear only in broadcasts; settings buttons each occupy their own row.
  Day selection uses embedded rich message buttons for published menus from today through the next 6 days;
  callback payloads contain fixed dates. In groups, `/yemek` is registered as an ephemeral command. Menu replies,
  day selection and rating edits are visible only to the requesting user. Ephemeral menus omit cleanup controls
  and scheduled deletion. For ordinary commands, bots without administrator rights show one public Open menu
  button; clicking it opens an ephemeral day selector. Private menus and broadcasts retain cleanup controls.
- **OBIS integration**: an aiogram FSM conversation collects a student's OBIS credentials, verifies them against
  the real OBIS login before saving (AES-GCM encrypted at rest), and lets the user fetch their current exam
  grades and lesson-attendance/skip-budget summary on demand — see `modules/obis/application/obis.py`,
  `modules/obis/infrastructure/client.py`, `modules/obis/infrastructure/parser.py`, `modules/obis/presentation/router.py`.
  User-requested grades and attendance send a regular loading message, then edit it into compact plain-text
  pages with standard inline navigation. Pages contain up to two subjects and are bounded by text length and
  line count. The last five multipage results per user are cached in FSM data by message ID, so page changes
  do not re-fetch OBIS or mix results from separate messages. Restarting the bot or clearing FSM data expires
  navigation; the callback asks the user to request fresh data. Scheduled OBIS notifications remain unchanged.
- **Notification settings**: a `⚙️ Settings` menu (`platform/telegram/routers/settings.py`) lets each user toggle five
  notification kinds (schedule changes, before-lunch/before-dinner menu pings, exam-grade changes, lesson skips),
  backed by a lazily-created `NotificationSettings` row per user that defaults every toggle to enabled — see
  `modules/notifications/settings.py` and the Food menu notification settings service.
- **Scheduled notifications** (the `jobs/` package, wired up in `jobs/scheduler.py`): the daily menu is broadcast to
  opted-in users at 11:00/17:00 Bishkek time; OBIS exam grades and lesson attendance are polled hourly per user
  and diffed against previously-seen state to notify only on actual changes; each tracked course's timetable is
  scraped hourly and diffed to notify trackers of schedule changes — see "Scheduled jobs & change detection"
  below.
- **Localization**: every user-facing string is served through aiogram's built-in gettext-based i18n, with the
  user's locale auto-detected from Telegram, falling back to Russian — see "Localization (i18n)" below.
- `/start` resolves the user's locale, upserts the Telegram user, and shows the main reply keyboard.
- **Advertising platform (барахолка)**: reached via the "🛒 Marketplace" main-menu button or a `/start market`
  deep link, both of which show a reply-keyboard sub-menu ("➕ Post an ad" / "📋 My ads" / "◀️ Back to menu",
  `modules/advertisements/presentation/advertisement.py::send_marketplace_menu`) with a link to the public channel
  (`Settings.advertisement_channel_link`) in the message text. An aiogram FSM collects a title, description,
  optional price/media/expiry, gated by a mandatory-contact check (Telegram username or a saved phone number),
  then submits the ad for moderation to a single shared moderation chat (`Settings.moderation_chat_id`) with
  Approve/Reject buttons (`modules/advertisements/presentation/advertisement_moderation.py`) — there is no per-user moderator role;
  anyone acting from that configured chat is authorized. Approving publishes the ad to a configured Telegram
  channel (`Settings.advertisement_channel_id`) rather than an in-bot browse feed, with contact details hidden
  behind a `/start ad_<id>` deep link (opens the bot, reveals the seller's contacts, and is logged), and
  rejecting can carry an optional comment shown to the ad's owner. Users manage their own ads (paginated list,
  detail, delete) under "📋 My ads" and their saved phone numbers under "⚙️ Settings → 📱 My phone numbers"; an
  hourly job (`modules/advertisements/jobs.py::cleanup_expired_advertisements_job`) deletes ads past
  their `expires_at` (chosen from fixed presets, not free text), removing their channel post(s) first — see
  "Advertising platform"
  below.
- **User feedback**: a "💬 Send feedback" row in the `⚙️ Settings` menu (`modules/feedback/router.py`) starts an
  aiogram FSM that collects a free-text message and forwards it to a single shared `Settings.admin_chat_id` chat;
  an admin answers by using Telegram's native "reply" on that forwarded message, and the bot relays the reply
  text back to the original user in *their* locale — see "Feedback & broadcast" below.
- **Broadcast**: an admin sends `/broadcast` in `Settings.admin_chat_id` (a command scoped to just that chat, not
  suggested in any other chat), then the next message they send is offered back as a preview with a
  Confirm/Cancel keyboard; confirming fans it out to every registered user, wrapped in a locale-appropriate
  "message from the administration" label resolved per recipient — see "Feedback & broadcast" below.

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
uv run pybabel extract -F babel.cfg -o src/manashelper/locales/messages.pot --no-location .
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

The app needs Postgres and these environment variables (see `src/manashelper/core/config.py`): `TELEGRAM_BOT_TOKEN`,
`DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD`, `OBIS_ENCRYPTION_KEY` (a base64-encoded 32-byte
AES-256 key used by `CryptoService` to encrypt stored OBIS passwords — generate one with
`python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"`), `ADVERTISEMENT_CHANNEL_ID`
(the chat id of the Telegram channel approved ads are published to — the bot must be an admin of that channel
with post rights), `ADVERTISEMENT_CHANNEL_LINK` (the channel's public `https://t.me/...` URL, shown as a link in
the in-bot marketplace menu — not derived from `ADVERTISEMENT_CHANNEL_ID`, since a numeric chat id alone isn't a
usable link), `MODERATION_CHAT_ID` (the chat id of the group/chat that receives new ads to Approve/Reject — the
bot must be a member with permission to send messages there; anyone acting from this chat is treated as
authorized, see "Advertising platform" below), `ADMIN_CHAT_ID` (the chat id of the group/chat used for user
feedback and for triggering broadcasts — the bot must be a member there; anyone acting from this chat is treated
as authorized, see "Feedback & broadcast" below), and optionally `DATASOURCE_HOST` (defaults to `db`, the
docker-compose service name — set to `localhost` for local dev outside Docker). `docker-compose.dev.yml` starts
only Postgres, exposed on host port `5432`. A local `.env` file (gitignored) is read automatically via
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

### Package layout (feature modules)

Feedback has moved to `modules/feedback/`, including its router, keyboards, callback types, application service,
repository, ORM and REQUEST-scoped provider. Advertisements has also moved to `modules/advertisements/`, with presentation, application, infrastructure,
domain enums and its own REQUEST-scoped provider. Its expiry job delegates to `ExpireAdvertisements` through
a publication-removal protocol and Telegram adapter. The planned migration of business areas to modules is complete.
The student survey is colocated in flat `modules/student_questions/`, including callbacks, FSM router,
application service, repository, ORM and REQUEST provider. Its deep link, overwrite behavior and stored formats are unchanged.
Release history is now in flat `modules/versions/`; its functions read `docs/versions/` on demand and keep
the same runtime path after relocation. It has no database table or DI provider.
Donations is now in flat `modules/donations/`, separating file catalog, Telegram QR adapter and application service.
Its provider retains an APP-scoped LRU cache and REQUEST-scoped service. Public `modules/users/queries.py`
supplies counts and recipient IDs to donations and broadcast.
Users now owns application locale/contact services, profile/phone infrastructure and language/phone presentation
under modules/users/. All its providers remain REQUEST-scoped. User retains OBIS credential columns and the
Schedule relationship; OBIS now owns credential persistence on that unchanged row.
EdersService reads credentials through ObisCredentialsService; tracking checks existence through UsersQuery.
EdersRepository retains credential eligibility SQL and the user-row lock protecting first observations.
Shared navigation functions live in platform/telegram/navigation.py, outside the start router.
Broadcast is colocated in flat `modules/broadcast/`: REQUEST-scoped SendBroadcast selects recipients through
UsersQuery and counts delivery results. TelegramBroadcastSender owns locale, HTML and Telegram API errors;
the router owns authorization, FSM and admin-facing messages.
Food menu lives in modules/food_menu/: application services, Telegram presentation, infrastructure and thin jobs.
Its provider retains APP client/parser and REQUEST services. BroadcastFoodMenu uses a Telegram sender boundary;
notification settings check users through UsersQuery.exists. Its repository initializes new lunch/dinner flags to True
before flush; the first meal/day toggle disables the selection immediately, preserving other saved preferences.
Schedule now lives in modules/schedule/ with catalog/tracking, timetable/search, infrastructure and thin jobs.
CourseTrackingRepository owns the tracked-course query; User ORM belongs to Users. SyncCourseTimetable selects
recipients through public modules/notifications/queries.py, whose provider retains REQUEST scope.
Notifications now lives in flat modules/notifications/: settings, ORM, repository and Telegram presentation.
Settings uses UsersQuery.exists; OBIS polling also selects recipients through NotificationRecipientsQuery.
Shared Settings navigation stays in platform/telegram/. NotificationSettingsRepository initializes all three flags to True
before flush; initial summaries reflect enabled defaults and the first toggle disables the selected flag.
Missing settings still opt users into notifications; do not depend on INSERT-time defaults when toggling new rows.
Shared weekday labels live in localization/weekdays.py; Bishkek timezone reuses
core/time.py. Root composition now has fourteen providers, including CoreProvider, TelegramPlatformProvider and ObisProvider.
Core owns shared config, logging, database factories/Base and resource lifecycle in core/.
The last legacy di.py was removed; StudyWeekProvider owns GetStudyWeek in REQUEST. Shared Telegram presentation and
infrastructure live in platform/telegram/: dispatcher, commands, navigation, filters, middleware, HTML/delivery,
audit and deletions. TelegramPlatformProvider keeps audit/deletion repositories and services in REQUEST.
Settings callbacks belong to platform/telegram/callbacks.py; Eders callbacks belong to its presentation package.
OBIS lives in modules/obis/: credentials/facade/notification/polling application code, infrastructure, presentation and jobs.
ObisProvider keeps client/crypto APP and repositories/services REQUEST. ObisCredentialsService is the public
read boundary for Eders, returning secrets with repr disabled and the unchanged SHA-256 ciphertext marker.
Shared OBIS login/new_http_client stay reused by Eders; no persistent session or new authentication flow is introduced.
PollObisUser delegates delivery through a real sender boundary; locale/HTML/API errors stay in the Telegram adapter.
First nonempty grades currently notify; first attendance rows remain silent. Encryption failures keep the pre-existing
student-number assignment order. Both behaviors are characterized and deliberately preserved in this refactor.
Eders lives in modules/eders/: application snapshot/filter/tracking/polling, infrastructure client/parser/URLs,
serialization/repository/ORM, Telegram presentation, jobs and provider. EdersProvider keeps client APP and other objects REQUEST.
PollEdersUser preserves refresh→locale→pending→send→ack. TelegramEdersNotificationSender formats all messages before sending,
groups materials, skips TelegramAPIError per message and yields successful events for immediate acknowledgement.
Unexpected failures abort only that user; the next user gets a separate request scope. Snapshot JSON, hashes,
account/schema baselines, monotonic observations and the one-retry OBIS SSO/AJAX flow are unchanged.
Eders exceptions are public in modules/eders/errors.py, keeping other features independent of HTTP/parser internals.
Study week lives in flat modules/study_week/: application.py, formatter.py, router.py and provider.py.
GetStudyWeek.execute reads Eders then Schedule, suppressing only NoTrackedCoursesError, and starts the seven-day summary
on the current Bishkek date. Its private /week router follows Eders immediately; Eders no longer imports Study week.
Sorting, HTML/chunking, source failure behavior and existing eders.* localization keys are unchanged.
The gettext adapter lives in platform/i18n/catalog.py; Locale/weekday labels stay in localization/.
Deletion jobs call MessageDeletionService.delete_due with an async delivery callable. The shared delete_messages
adapter uses itertools.batched, skips TelegramAPIError per batch and lets unexpected errors abort the sweep.
The same adapter removes advertisement publications. Runtime commands/locales paths are covered for Docker-like layouts.
`docs/ARCHITECTURE.md` describes the current state; `docs/MIGRATION.md` records stage boundaries and baseline issues.

Under `src/manashelper/`, migrated features own their code in `modules/`; shared infrastructure lives in `core/`
and `platform/`. `bootstrap.py` loads ORM explicitly and `jobs` wires the scheduler. `core/time.py` owns BISHKEK_TZ;
Schedule's application package owns text_normalization.py. Empty bot/services/repositories/scraping packages were removed.

**Services return plain dataclasses, never ORM models.** An application method called from a feature's router
returns a frozen `dataclass` (e.g. `FacultyModel`, `DepartmentSummary`, `CourseSummary`) or raises, never a
SQLAlchemy model instance — routers must never hold an ORM object. Map ORM model → dataclass with a private
module-level helper next to the service class (see `course._to_summaries`, used by `CourseService`).

**Application services exist to hold DI-injected collaborators, not as Java-style ceremony.** A `*Service` class's
`__init__` takes the repositories (and other collaborators, e.g. `CryptoService`, `ObisClient`) it needs and
stores them as attributes; its methods are the only thing a router or a `jobs/` module depends on via
`FromDishka[...]`/`request_container.get(...)` — the presentation layer never sees a repository, an `AsyncSession`,
or `Settings` directly, only the service. Pure helper logic that doesn't touch `self` (formatting, mapping a
scraped/ORM object to a dataclass) is a private module-level function, not a `@staticmethod` — see
`course._to_summaries` or `obis._to_exams_model`.

### Telegram update handling (aiogram routers)

Each feature area is an aiogram `Router` (`platform/telegram/routers/start.py`, `modules/schedule/presentation/routers/timetable.py`), included into the
`Dispatcher` in `platform/telegram/dispatcher.py`. Unlike the old Java chain-of-responsibility (`shouldHandle`/`handle` over a flat handler
list, first match wins), aiogram matches each incoming update against filters declared on `@router.message(...)` /
`@router.callback_query(...)` decorators — still effectively first-match-wins across included routers, so keep
filters mutually exclusive the same way the Java handlers' `shouldHandle` predicates had to be.

Callback data is packed via aiogram's typed `CallbackData` factories (feature-local callbacks.py —
`FacultyCallback`/`DepartmentCallback`/`CourseCallback`), replacing the old `CallbackDataByIdFilter.pack`/
`.parseUUID`/`.parseInt` string convention — `SomeCallback.filter()` is passed directly to
`@router.callback_query(...)`, and the parsed instance is injected into the handler as a `callback_data: SomeCallback`
parameter.

### Concurrency: per-chat ordering

aiogram's `Dispatcher.start_polling` dispatches each update as its own `asyncio` task by default
(`handle_as_tasks=True`), so two updates from the *same* chat could run concurrently unless something serializes
them. `platform/telegram/middlewares/per_chat_ordering.py::PerChatOrderingMiddleware` (registered as an outer middleware on both
`dispatcher.message` and `dispatcher.callback_query`) holds one `asyncio.Lock` per chat id so a chat's updates
process strictly in order — this matters because `CourseService.toggle_tracked_course`'s tracked-courses
read-modify-write isn't safe under concurrent access for the same user. This is the Python analog of the Java
`TelegramConsumer`'s per-chat `CompletableFuture` chaining over a virtual-thread executor.

### Dependency injection (Dishka)

`core/provider.py` defines CoreProvider: Settings, AsyncEngine, async_sessionmaker and the shared HTTP client
have APP scope, and AsyncSession has REQUEST scope. Each feature owns its provider; the old `di.py` was removed.
`setup_dishka(container, dispatcher)` +
`inject_router(dispatcher)` in `platform/telegram/dispatcher.py` wire dependency injection into router handlers via `FromDishka[X]`
parameter annotations — the analog of Spring's constructor injection into `@Component`/`@Service` beans. The
CoreProvider's session provider commits only on successful finalization. An escaping body exception/cancellation
or a failed/cancelled commit triggers rollback; the session still closes. Dishka sends the scope exception via
asend(), so the provider explicitly inspects the yielded value. A handled error inside the scope still permits commit.
Regression tests in `tests/core/test_core_transactions.py` cover real PostgreSQL savepoints, cancellation, aiogram error middleware
and cleanup failures; `tests/modules/feedback/test_feedback_composition.py` verifies feature composition. Feature providers share the REQUEST session.

**Do not use `dishka.integrations.aiogram.setup_dishka(..., auto_inject=True)`.** As of dishka 1.10.1 + aiogram
3.31, it registers its handler-injection pass as a `router.startup` callback via
`functools.partial(inject_router, router=router, ...)`, but aiogram's `Router.emit_startup` always injects its own
`router=self` kwarg into every startup callback — colliding with the partial's bound `router` kwarg and raising
`TypeError: inject_router() got multiple values for argument 'router'`. Instead call
`setup_dishka(container, dispatcher)` (no `auto_inject`) followed by an explicit `inject_router(dispatcher)`, as
done in `platform/telegram/dispatcher.py` — confirmed working end-to-end against a real dispatcher, including through to a genuine
Telegram API call.

### Data layer

Alembic (`alembic/versions/*.py`) is the source of truth for schema — this is a fresh start, not a port of the old
Flyway migration history, though the seed data (faculties/departments/courses) was carried over from the Java
project's `V2__seed_faculties_and_departments.sql` into `e82d16133698_seed_faculties_departments_courses.py`.
`alembic/env.py` points `target_metadata` at `manashelper.core.database.Base.metadata` and overrides `sqlalchemy.url`
from `Settings.database_url` at runtime — `alembic.ini`'s `sqlalchemy.url` placeholder is never actually used.
The `db` package and global ORM re-exports were removed. Import each model from its owning feature/platform module.
`bootstrap.load_models()` registers all model modules and configures relationships at main/Alembic/test bootstrap;
standalone compositions must call it before using ORM. Imports of individual repositories no longer load all models.
Migrations run automatically on boot (`main.py::run_migrations`, called before `asyncio.run(main())` — mirrors the
old `FlywayConfig`'s `initMethod=migrate` bean) as well as being runnable manually via `uv run alembic upgrade head`.

Add new migrations with `uv run alembic revision --autogenerate -m "..."` after changing a model under
the owning feature/platform ORM module. Register a new model module in bootstrap.py, then review generated operations.

### Tests

`tests/conftest.py` provides a `session` fixture: each test runs inside a transaction opened on a dedicated
connection, with the `AsyncSession` bound via `join_transaction_mode="create_savepoint"` so that even if the code
under test calls `session.commit()`, only a SAVEPOINT is released — the outer transaction is always rolled back
after the test, so tests can freely insert rows (including ones that collide in shape with seeded catalog data,
as long as ids don't collide) without polluting the dev database. Tests run against the real dev Postgres
(`docker-compose.dev.yml`), not SQLite — avoids dialect drift on native `UUID`/`TIMESTAMP` types.

The 55 test modules are grouped under `tests/modules/<feature>/`, `tests/core/` and `tests/platform/{telegram,i18n}/`.
Run a feature with `uv run pytest tests/modules/eders/`. Shared resource anchors live in `tests/paths.py`;
fixtures data stays in `tests/fixtures/` for both pytest and HTTP mocks. Eders factories and its tracking fixture
live in `tests/modules/eders/factories.py` and local conftest.py, without imports from another test module.

### OBIS integration notes

`ObisClient` (`modules/obis/infrastructure/client.py`) opens a fresh `httpx.AsyncClient` per call (base URL
`https://obistest.manas.edu.kg`, `follow_redirects=True`) rather than keeping a persistent per-chat session like
the Java `ObisSession`/`ObisSessionManager` did — OBIS is re-authenticated on every attendance/exam-grade fetch
anyway (see `ObisService`), so there is no session reuse to preserve, and this avoids an unbounded
`dict[chat_id, session]` growing for the process lifetime. Credentials are collected via an aiogram FSM
(`modules/obis/presentation/router.py::ObisCredentialsForm`, `MemoryStorage` — fine for a single-process deployment; move to
`RedisStorage` if the bot ever runs multi-worker) rather than the Java version's external Telegram WebApp form,
and are verified against a real OBIS login before being persisted. Passwords are encrypted at rest with AES-GCM
(`CryptoService`) instead of the Java version's raw AES-ECB.

### Localization (i18n)

All user-facing text is translated via aiogram's built-in `aiogram.utils.i18n` (a thin wrapper over GNU gettext,
requiring the `Babel` package — see the `aiogram[i18n]` extra in `pyproject.toml`). Call sites use stable message
keys such as `_("menu.settings")` (`from aiogram.utils.i18n import gettext as _`) or, for count-dependent text,
`ngettext("obis.skips_left.one", "obis.skips_left.many", n)`. Keep keys literal so Babel can extract them.
All text, including English, lives in `src/manashelper/locales/<locale>/LC_MESSAGES/messages.{po,mo}` for
`en`/`ru`/`ky`/`tr`/`zh` (simplified Chinese). `CatalogI18n` adds the English catalog as a fallback for missing
translations and unsupported rendering locales, so a missing translation does not display a message key.
Command JSON files in `docs/commands/` also contain description keys; the custom extractor in `babel.cfg`
includes those when extraction runs from the repository root with `.` as its input directory.
`*.po` files are the hand-translated source of truth and are committed; `*.mo` files are compiled build artifacts
and are gitignored (compiled by `docker/Dockerfile` and by CI — see Commands above — anyone running the bot or
test suite locally must run `pybabel compile` after cloning or after editing a `.po` file).

`localization/locale.py::Locale` is the supported-locale enum (`ky`/`ru`/`en`/`tr`/`zh`); `platform/i18n/catalog.py` holds
the single process-wide `I18n` instance. `User.locale` (nullable `String(2)`) persists a user's resolved locale.
`platform/telegram/middlewares/i18n.py::LocaleMiddleware` (registered *after* `setup_dishka` in `platform/telegram/dispatcher.py`, so it can use the
request-scoped container) runs on every update: it upserts the user via `modules/users/application/locale.py::LocaleService`,
which returns the saved locale if there is one, otherwise auto-detects one from
`message.from_user.language_code` (`localization/locale.py::resolve_from_language_code`), falling back to
`DEFAULT_LOCALE` (Russian) when that language code is missing or unsupported — the resolution always succeeds,
so there is no picker shown on this path. The middleware then enters `i18n.context()` / `i18n.use_locale(...)`
and calls the handler inside it, so every `_()`/`ngettext()` call made anywhere during that update — filters,
handlers, keyboards, formatters — resolves against the right locale via the contextvar aiogram's `I18n` keeps,
with no `Translator`/locale parameter threaded through call signatures. `platform/telegram/filters/translated_text.py`
(`TranslatedText`) exists because a reply-keyboard button's label is only known once translated, so matching the
incoming message text against a hardcoded string (`F.text == "..."`) can't work across locales.

Jobs (the `jobs/` package) run outside any Telegram update, so there's no ambient middleware to set the gettext
context; each per-recipient send there looks up that user's `Locale` and wraps its own `format_...(...)` call in
`with i18n.context(), i18n.use_locale(locale.value): ...` explicitly. A user can still change their locale
explicitly at any time via `/language` or the "🌐 Language" row in Settings (`modules/users/presentation/routers/locale.py`), which
shows the 5-language picker (`modules/users/presentation/keyboards/locale.py`) with names rendered from each language's own catalog —
the only place that picker is shown, now that
auto-detection never falls through to it.

### Scheduled jobs & change detection

`jobs/scheduler.py` registers the `AsyncIOScheduler` job functions from their owning modules, one module per
feature area (`modules/food_menu/jobs.py`, `modules/obis/jobs.py`, `modules/schedule/jobs.py`,
`platform/telegram/deletions/jobs.py`, `modules/advertisements/jobs.py`), plus `platform/telegram/delivery.py` for cross-cutting helpers
shared by more than one job (`send_notification`, `delete_messages` for batched
`deleteMessages` calls). Each job opens its own short-lived Dishka request scope(s)
(`async with container() as request_container`) rather than reusing one across the whole run, and wraps its body
in a broad `except Exception: logger.exception(...)` so one failure (a bad HTML page, a dead OBIS login, a user
who blocked the bot) never aborts the rest of the batch — the same resilience shape as the pre-existing
`sync_daily_menus_job`. Per-recipient Telegram sends are wrapped individually in `except TelegramAPIError` for
the same reason.

Three notification-producing jobs all follow one pattern: keep a Postgres table of the *last known state* per
(user or course, item), diff a freshly scraped/fetched snapshot against it, persist the new state, and only
notify on changes. Timetable/attendance first observations are silent; the existing OBIS grade behavior is an
exception: a first nonempty score already notifies, as the characterization tests record.

- **Timetable sync** (`modules/schedule/application/timetable_sync.py`, hourly): `modules/schedule/infrastructure/timetable_client.py` +
  `modules/schedule/infrastructure/timetable_parser.py` scrape `http://timetable.manas.edu.kg/department-printer/{course_id}` (plain
  HTTP, no auth — the site has no HTTPS listener) for every `Course.id`, parsed into one `Lesson` row per
  (course, weekday, time slot) holding a normalized "code name — teacher, room" string; a changed/added/removed
  slot notifies every tracker with `schedule_changes_enabled`.
- **OBIS exam grades & lesson skips** (`modules/obis/application/notification.py`, hourly, one poll per user):
  reuses `ObisService.get_exam_grades`/`get_attendance` (so it's re-login-per-poll like every other OBIS call),
  diffing against `UserExamGrade` (per user+lesson_code+exam_name) and `UserLessonAttendance` (per
  user+lesson_code) rows; a user with no saved OBIS credentials is skipped cheaply (a local DB check) before any
  network call, so polling every user hourly is safe.
- **Daily menu broadcast** (`modules/food_menu/jobs.py::broadcast_lunch_menu_job`/`broadcast_dinner_menu_job`, cron
  11:00/17:00 `Asia/Bishkek`): sends the same rich message with embedded menu rating buttons used for `/yemek` to
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
  `modules/advertisements/presentation/advertisement_moderation.py::_is_moderation_chat` checking that the callback/message's
  `chat.id` matches that configured chat — not by anything stored per-user — so adding/removing moderators is
  purely a matter of who's a member of that Telegram chat.
- **No in-bot browse feed**: approved ads are published to a Telegram channel
  (`Settings.advertisement_channel_id`) instead of a bot-side listing screen a user could browse. Every
  `AdvertisementChannelMessage` row records a published message id so the channel post(s) can be removed again
  when the ad is deleted or expires (a media-group publish yields one message per photo/video).
- **SQL-side pagination**: `AdvertisementRepository.get_page_by_user_id` does real `LIMIT`/`OFFSET` pagination for
  "📋 My ads", unlike every other paginated screen in the bot (`versions.py`, `lesson_search.py`), which slices an
  already-fully-fetched in-memory list — a persistent management list needs to reflect deletes immediately.
- **User-uploaded media**: `modules/advertisements/presentation/advertisement.py`'s `AdvertisementForm.media` state is the only place in
  the bot that receives (rather than sends) Telegram photos/videos, storing each `file_id` in
  `AdvertisementMedia` (capped at 10 per ad, tracked in FSM state until submission). Sending a 10-item album
  delivers 10 separate updates, one per photo/video — rather than replying to each one, `_render_media_prompt`
  edits a single tracked message in place for the running count, relying on `PerChatOrderingMiddleware` already
  serializing every update for that chat (so there's no debounce/race handling to get wrong).
- **Contact gate**: posting is blocked until the user has at least one contact method. A Telegram username is
  read live off `User.username` (already kept fresh by `LocaleMiddleware`'s per-update upsert, so no extra Bot
  API call is needed); phone numbers are collected inline at the start of the posting flow (reply-keyboard
  `request_contact` button or manual entry, validated by `UserContactService.is_valid_phone_number`) and
persisted in `UserPhoneNumber` — see `modules/users/application/user_contact.py`. Users manage their saved numbers (add/delete)
  from `⚙️ Settings → 📱 My phone numbers` (`modules/users/presentation/routers/phone_numbers.py`), which reuses the same
  contact-request keyboard (`modules/users/presentation/keyboards/phone_numbers.py`) as the posting flow.
- **The marketplace menu is a reply keyboard, not an inline one** (`modules/advertisements/presentation/keyboards/advertisement.py::
  build_advertisement_menu_keyboard`), unlike almost every other sub-menu in the bot — it needs to stay on
  screen across the whole "post an ad" / "my ads" sub-flow the way the main reply keyboard does, and it's
  reachable two ways: the "🛒 Marketplace" main-menu button, and a `/start market` deep link
  (`modules/advertisements/presentation/advertisement_contact.py::MARKET_DEEPLINK_PAYLOAD`, handled by the same
  `CommandStart(deep_link=True)` handler as the `ad_<id>` contact-reveal payload) — both call the shared
  `send_marketplace_menu` in `modules/advertisements/presentation/advertisement.py` so the menu text/keyboard can't drift between the
  two entry points. "◀️ Back to menu" restores the main reply keyboard. A reply-keyboard button's label can't
  carry a URL (unlike an inline button), so the link to the public channel (`Settings.advertisement_channel_link`)
  is instead an `<a href="...">` in the menu message's own text.
- **Contacts are hidden on the public channel post**, unlike the poster's own confirm preview and the
  moderation chat's review message (both closed audiences, which see raw contact details via
  `format_advertisement(..., contact=...)`). The channel post instead embeds a bot deep link
  (`format_advertisement(..., contact_deep_link=...)`, built from `bot.get_me()` in
  `advertisement_moderation.py::on_approve` as `https://t.me/<bot>?start=ad_<id>`). Opening it is handled by
  `modules/advertisements/presentation/advertisement_contact.py` (`CommandStart(deep_link=True)`, registered in `platform/telegram/dispatcher.py` *before*
  `start_router` so a bare `/start` still falls through to the normal welcome flow) via
  `AdvertisementContactService.reveal_contact`, which also logs the open as an `AdvertisementContactView` row
  (never deduplicated — every open is its own row, for counting interest).
- **Expiration is chosen from fixed presets** (45 minutes / 6 hours / 24 hours / 7 days / no expiration —
  `AdvertisementExpiryCallback`), not free-text date entry.
- **HTML escaping**: `platform/telegram/html.py::escape_html` (a thin wrapper over aiogram's
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
  per-chat token-bucket throttle in `platform/telegram/middlewares/rate_limit.py`.
- **Moderation**: a new ad is sent once to `Settings.moderation_chat_id` with Approve/Reject buttons
  (`modules/advertisements/presentation/advertisement_moderation.py`); both actions re-check the ad is still `pending` before acting
  (`AdvertisementNotPendingError`) so two people tapping at once in that chat can't double-process the same ad.
- **Expiration cleanup**: `modules/advertisements/jobs.py::cleanup_expired_advertisements_job` (hourly) deletes ads past
  `expires_at`, removing their channel post(s) first — same outbox-sweep shape as
  `platform/telegram/deletions/jobs.py::cleanup_scheduled_message_deletions_job`.

### Feedback & broadcast

Another from-scratch subsystem (no Java precedent), both built around the same single shared
`Settings.admin_chat_id` and, like the advertising platform, with no per-user admin role — authorization is
purely "did this update originate from that chat" (`modules/feedback/router.py::_is_admin_chat`,
`modules/broadcast/router.py::_is_admin_chat`).

- **Reply-based correlation, not an in-bot reply UI**: `FeedbackMessage` (`modules/feedback/orm.py`) stores
  the id of the message a feedback submission was forwarded as in the admin chat
  (`admin_chat_message_id`). An admin answers with Telegram's native "reply" feature on that forwarded message;
  `modules/feedback/router.py::on_admin_reply` matches on `message.reply_to_message.message_id` against that column
  (`FeedbackRepository.get_by_admin_chat_message_id`) to find which user to relay the answer to — there's no
  in-bot "answer" button or form. Every feedback submission is independent: there's no back-and-forth threading
  beyond one submit/one reply, so a user who wants to say more just submits feedback again.
- **Locale correctness**: the admin's reply text is rendered in the *recipient's* locale
  (`LocaleService.get_locale`), not the replying admin's own — the same
  `i18n.use_locale(...)`-wraps-a-builder shape as `advertisement_moderation.py::_notify_owner`. The admin chat
  itself (the feedback-forwarding message, confirmations, the broadcast composition flow) always renders in
  `DEFAULT_LOCALE`, being a single shared destination rather than a specific recipient — same reasoning as
  `advertisement.py::_notify_moderation_chat`.
- **Broadcast is a plain fan-out to every registered user**, not gated by any per-feature `NotificationSettings`
  toggle (those are for the bot's own recurring notifications, not one-off admin announcements) — see
  `modules/broadcast/router.py::on_broadcast_confirmed` delegates to `SendBroadcast.execute`, which selects
  recipient IDs through public UsersQuery and sends sequentially through BroadcastSender. The concrete
  TelegramBroadcastSender wraps raw text in a locale-appropriate "message from the administration" label,
  using the same per-recipient `i18n.context()`/`i18n.use_locale()` shape as
  `modules/food_menu/jobs.py`'s broadcasts (this one just runs from a bot command handler instead of a scheduled job,
  since it's an ad-hoc admin action rather than a recurring one).
  FSM clears before recipient lookup. TelegramAPIError from send skips one recipient without retry;
  locale lookup failures and unexpected exceptions propagate and prevent the final summary, as before.
- **`/broadcast` is registered against `BotCommandScopeChat(chat_id=settings.admin_chat_id)`**
  (`platform/telegram/command_catalog.py::build_admin_commands`, wired up in `platform/telegram/commands.py::setup_commands`), not any of the
  "all chats" scopes every other command uses — it shouldn't show up as a suggestion in random group chats the
  bot happens to be added to, only in the one chat where it's actually authorized.
- **HTML escaping**: both the admin's broadcast text and feedback bodies/replies go through
  `platform/telegram/html.py::escape_html` before being interpolated into an HTML-parse-mode message, same
  correctness reasoning as the advertising platform (an unescaped bare `&`/`<`/`>` makes Telegram reject the
  whole `sendMessage` call).

### Student questions survey

The private deep link `/start student_questions` opens a localized survey about students' course,
university questions, answer sources and interest in an experimental bot beta. Questions 3–5 are
conditional. Completed responses are stored in `student_questions_responses`, with the Telegram user
ID as the primary key. A second submission requires explicit confirmation and replaces the old response
only when the new survey finishes; cancellation leaves the existing response intact. Incomplete drafts
use FSM memory and are lost on restart. Callback session IDs reject buttons from previous runs.
The survey router precedes the advertisement deep-link router, which otherwise claims every start payload.

## Roadmap (not yet ported from the Java version)

- **About screens**: static informational callback handlers.
