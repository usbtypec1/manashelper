# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Manashelper is a Telegram bot (Spring Boot 4 / Java 25) for Manas University students. There is **no REST API** in
this codebase — despite the README mentioning OpenAPI/Swagger, no `@RestController` exists. All user interaction
happens through Telegram long-polling.

This is a **multi-module Maven project**: the root `pom.xml` is an aggregator/parent (packaging `pom`, no source of
its own) holding shared build config — Checkstyle (bound directly so every module is checked the same way without
redeclaring it) and `dependencyManagement`/`pluginManagement` for cross-module infra like Lombok/MapStruct.
`manashelper-bot/` is the (currently only) module and contains the entire bot described below. Expect more sibling
modules under the root later — when adding one, give it its own `pom.xml` with `<parent>` pointing at the root and
add it to the root's `<modules>`; don't put module-specific dependencies (telegrambots, jsoup, springdoc, ...) into
the root — those stay local to the module that needs them.

Core capabilities:

- **Timetable**: scrapes the university timetable site, stores faculties/departments/courses/lessons, and notifies
  tracked users of schedule changes.
- **OBIS integration**: logs into the university's student portal (obistest.manas.edu.kg) on the user's behalf
  (credentials stored AES-encrypted) to fetch attendance and exam grades.
- **Daily cafeteria menu**: scrapes and caches the daily menu, with per-dish user ratings.
- **Background jobs**: `@Scheduled` jobs synchronize lessons (hourly) and the daily menu (every 10 min).

## Commands

There is no Maven wrapper in this repo — use a system-installed `mvn` (Java 25; the Dockerfile build/runtime images
are `eclipse-temurin:25`).

Run these from the repo root — Maven resolves the reactor and, for `-pl`, the target module — or `cd
manashelper-bot` first and drop the `-pl manashelper-bot`:

```
mvn clean verify                                  # builds the whole reactor: compile, tests, Checkstyle for every module
mvn test -pl manashelper-bot                       # run tests only, just this module
mvn test -pl manashelper-bot -Dtest=CourseLessonFormatterTest              # run a single test class
mvn test -pl manashelper-bot -Dtest=CourseLessonFormatterTest#addedLesson_shouldUseUnknownDay_whenWeekdayIsZero
mvn -pl manashelper-bot spring-boot:run            # run the bot locally (needs env vars below + a Postgres instance)
mvn checkstyle:check                               # Checkstyle only, whole reactor
```

Checkstyle enforces: 120-char line length, no unused imports, no star imports, naming conventions
(types/methods/parameters), and consistent indentation/whitespace. Its config (`checkstyle.xml`, at the repo root)
is shared by every module — a violation in any module fails `mvn verify` (and thus the Docker build).

### Running locally

The app needs Postgres and these environment variables (see `manashelper-bot/src/main/resources/application.yml`):
`DATASOURCE_NAME`, `DATASOURCE_USERNAME`, `DATASOURCE_PASSWORD`, `CRYPTO_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`,
`SERVER_PORT`. `docker-compose.dev.yml` starts only Postgres, exposed on host port `5433`, matching
`application-dev.yml`'s datasource URL — use the `dev` Spring profile locally. `docker-compose.yml` runs the full
stack (app + db) against a prebuilt image, driven by a `.env` file.

Deployment: pushing a `v*` tag triggers `.github/workflows/ci-cd.yml`, which runs the Docker multi-stage build
(which itself runs `mvn clean verify`) and pushes `usbtypec1/manashelper:<version>` and `:latest` to Docker Hub.
There is no automated deploy step beyond the image push.

## Architecture

### Package layout (by layer, not by feature)

Within the `manashelper-bot` module, code is organized under `kg.manasuniversity.usbtypec.manashelper` by
technical layer, not by feature domain:
`controller` (Telegram handlers), `service` (business logic, session management, formatters), `client` (raw HTTP
fetch of external HTML pages), `parser` (HTML → model), `mapper` (entity ↔ model), `entity` (JPA), `repository`
(Spring Data), `model` (DTOs/records), `job` (`@Scheduled` tasks), `exception`, `config`. Every package is flat —
there are no per-feature subpackages (no `timetable/`, `foodmenu/`, `user/`); a class's name, not its folder,
tells you which feature it belongs to (e.g. `CourseService`, `DailyMenuService`, `ObisService` all live directly
in `service/`).

**Services return models, never entities.** `@Service`/`@Component` classes that a `controller` handler calls
must return `model` records (or `void`), not `entity` types — controllers/handlers must never hold a JPA entity.
Map entity → model at the bottom of the service method (see `DailyMenuMapper`, `CourseService.toSummaries`), not
in the controller. The internal timetable-sync pipeline (`LessonBuilderService`, `LessonChangeDetector`,
`LessonSynchronizeService`) is the one intentional exception: those collaborate with each other purely to
build/diff/persist `Lesson` entities and are never called from `controller`, so there's no boundary to protect
there — don't spread that pattern to anything a handler touches.

### Telegram update handling (chain of responsibility)

Every bot interaction is a `TelegramUpdateHandler` (`controller/TelegramUpdateHandler.java`): an abstract Spring
`@Component` with `shouldHandle(Update)` / `handle(Update)`. `TelegramConsumer` (the
`LongPollingSingleThreadUpdateConsumer` registered with `TelegramBotConfig`) iterates over *all* handler beans in
injection order and dispatches to the first whose `shouldHandle` returns true, then stops. There is no explicit
priority/ordering mechanism — when adding a new handler, make sure its `shouldHandle` predicate doesn't
accidentally shadow (or get shadowed by) an existing one. All handlers sit flat in `controller/`; group by name
prefix (`Obis*`, `FoodMenu*`, `About*`, `Course*`/`Department*`/`Faculty*`) rather than by folder.

Handlers must go through a `service` for any data access — see `FacultyService`/`DepartmentService`/
`CourseService`, which replaced four handlers that used to inject `*Repository` and manipulate entities directly.

Callback button data is packed as `"<CallbackData enum name>:<id>"` strings (see `CallbackDataByIdFilter.pack` /
`.parseUUID` / `.parseInt`) and matched back in `shouldHandle`. Free-text, multi-step flows (e.g. entering OBIS
credentials) are tracked per-chat in-memory via `ObisSessionManager` rather than callback data, since they need to
capture the next arbitrary text message.

### Concurrency: virtual threads

`spring.threads.virtual.enabled: true` (`application.yml`) puts `@Scheduled` jobs (`SynchronizeLessonsJob`,
`SynchronizeDailyMenusJob`) and the embedded Tomcat connector on virtual threads — relevant because handler/job
code makes blocking calls (`RestClient` requests) rather than being reactive end-to-end.

`TelegramConsumer` overrides the library's default `consume(List<Update>)`, which otherwise funnels *every* chat's
updates through one shared background thread (`LongPollingSingleThreadUpdateConsumer.updatesProcessorExecutor`).
Instead it dispatches each update onto `Executors.newVirtualThreadPerTaskExecutor()`, chained per chat id via
`CompletableFuture` so a single chat's updates still process in receipt order (important: `ObisSession`'s
`CookieManager` and `User`'s tracked-courses read-modify-write in `CourseService` aren't safe under concurrent access for the
*same* chat), while different chats now run concurrently instead of queueing behind one slow OBIS call. When
adding new per-chat mutable state, keep it keyed by chat/user id (like `ObisSessionManager`) — don't assume a
single global thread serializes access to it anymore.

### Scraping + sync pattern

Both the timetable and food-menu sync pipelines follow the same shape for pulling in external university data: a
`client` class (Jsoup/RestClient HTTP call to the university site, returns raw HTML) → a `parser` class (HTML → a
`model` record, no persistence knowledge) → a `job`/`service` that diffs the parsed result against stored entities
and only writes on actual changes (`LessonChangeDetector` for lessons, name-set comparison in
`SynchronizeDailyMenusJob` for menus). Follow this same shape for any new scraped data source rather than writing
directly from the parser into the repository — new classes go straight into the top-level `client`/`parser`/`job`
packages, not a new feature subpackage.

### OBIS session handling

`ObisService` (in `service/`) decrypts the user's stored password (`CryptoService`, AES via `crypto.secret-key`),
re-authenticates against OBIS per-request (`ObisClient.sendLoginRequest`, in `client/`), and then fetches the
target page. Each Telegram chat gets its own cookie-jar-backed `RestClient` session (`ObisSession`, held per-chat by
`ObisSessionManager`, both in `service/`) since OBIS auth is cookie-based and stateful — don't share
`RestClient`/cookies across users.

### Data layer

Flyway (`manashelper-bot/src/main/resources/db/migration/V*__*.sql`) is the source of truth for schema; JPA
`ddl-auto` is `none`.
Add new migrations rather than editing entities' `@Column` mappings alone. `FlywayConfig` runs migrations with
`baselineOnMigrate(true)`.

## Further docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — deeper dive: data model, update/OBIS request flows, formatting
  layer.
- [`docs/guides/`](docs/guides/) — step-by-step recipes for adding a Telegram handler, a scraped data source, or a
  DB migration.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — candidate/in-flight feature list (template — not yet populated).
