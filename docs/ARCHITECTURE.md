# Architecture

This is a reference document for how Manashelper is put together. For day-to-day commands and conventions, see
[`../CLAUDE.md`](../CLAUDE.md). Start there; come here when you need the full picture before adding a feature.

## Repo shape: multi-module Maven

The root `pom.xml` is an aggregator/parent (`packaging: pom`) — no source, no runnable app of its own. It holds
build config meant to be shared across modules: Checkstyle is bound directly in its `<build><plugins>` (not
`pluginManagement`), so it's inherited and runs the same way for every module without that module redeclaring it;
`dependencyManagement`/`pluginManagement` centralize Lombok/MapStruct versions for any module that wants them.
Everything described in this document below "Runtime shape" lives in the `manashelper-bot` module (its own
`pom.xml`, `<parent>` pointing at the root). More sibling modules are expected — see `../CLAUDE.md` for the rule
on where new module-specific dependencies belong (in the module, not the root).

## Runtime shape

Manashelper is a single Spring Boot process with three moving parts:

1. **Telegram long-polling client** (`config/TelegramBotConfig`) — the only inbound entry point. There is
   no HTTP API surface (no `@RestController` anywhere in the codebase, despite the top-level `README.md`
   mentioning Swagger/OpenAPI — springdoc is on the classpath but has nothing to document).
2. **Scheduled jobs** (`@EnableScheduling` in `ManashelperApplication`) — pull data from the university's public
   sites on a timer and write to Postgres.
3. **Postgres**, schema-owned by Flyway, accessed through Spring Data JPA repositories.

There's no message queue, no cache layer, no separate worker process — jobs and the bot consumer run as beans in
the same JVM.

## Layer map

Code is split by *technical layer*, not by feature domain — every package below is flat (no per-feature
subfolders); a class's name tells you its feature, its package tells you its role:

| Package | Owns | Notes |
|---|---|---|
| `controller` | Every `TelegramUpdateHandler` (plus `TelegramConsumer`) — the presentation layer | No entities, no repositories; only talks to `service` |
| `service` | Business logic, session/state management, formatting | Must return `model` records (or `void`) to `controller`, never `entity` types — see "Services return models" below |
| `client` | Raw HTTP fetch of external HTML pages (`DailyMenuClient`, `TimetableClient`, `ObisClient`) | No parsing, no persistence |
| `parser` | HTML → `model` record (`DailyMenuParser`, `TimetableParser`, `TimeRangeParser`, `ObisParser`) | No Spring/JPA dependencies, so parsers are directly unit-testable |
| `mapper` | Entity ↔ model conversion (`DailyMenuMapper`, `DishMapper`, `LessonMapper`) | |
| `entity` | JPA `@Entity` classes (`Course`, `Department`, `Faculty`, `Lesson`, `DailyMenu`, `DailyMenuRating`, `Dish`, `User`) | Never referenced outside `service`/`repository`/`mapper` |
| `repository` | Spring Data JPA repositories | Only `service` classes inject repositories |
| `model` | DTOs/records returned by services and consumed by controllers | Includes parser output (`CourseTimetable`) and view models (`DailyMenu`, `CourseSummary`, ...) |
| `job` | `@Scheduled` sync tasks | |
| `exception` | Domain exceptions | |
| `config` | Cross-cutting Spring config (`FlywayConfig`, `JpaConfig`, `TelegramBotConfig`) | |

`controller` is allowed to depend on `service`, `model`, and `exception` — never directly on `entity` or
`repository`. `service` is the only layer allowed to depend on `repository`/`entity`/`mapper`. Keep it that way:
business/scraping logic should be Telegram-agnostic and testable without bot infrastructure, and controllers
should never be able to leak a lazy-loaded JPA proxy into a Telegram reply.

### Services return models

Any `service` class a `controller` handler calls must return a `model` record (or `void`) — never an `entity`.
`FacultyService`, `DepartmentService`, and `CourseService` exist specifically to enforce this for the
faculty/department/course-tracking flow, which previously had *no* service layer at all: `CourseDetailHandler`,
`CourseListHandler`, `DepartmentListHandler`, and `FacultyListHandler` used to inject `CourseRepository`/
`UserRepository`/`DepartmentRepository`/`FacultyRepository` directly and mutate `Course`/`User` entities in the
controller. If you're adding a new handler that needs data, add or extend a `service` method that returns a
`model` — don't inject a repository into a `controller` class.

The one intentional exception is the internal timetable-sync pipeline: `LessonBuilderService`,
`LessonChangeDetector`, and `LessonSynchronizeService` pass `Lesson`/`Course` entities between each other to
build/diff/persist the synced lesson set. None of them are ever called from `controller` — they're pure
persistence-orchestration helpers — so there's no controller-facing boundary to protect there. Don't use that as
precedent for a new controller-facing service.

## Data model

```
faculties ──< departments ──< courses ──< lessons
                                              (synchronization_id groups one sync run's rows)
users ──< user_courses >── courses        (which courses a user tracks — see note below)
users ──< daily_menu_ratings >── daily_menus ──< daily_menu_dishes >── dishes
```

Notes on the schema (`manashelper-bot/src/main/resources/db/migration/`):

- **`lessons.synchronization_id`**: each run of `SynchronizeLessonsJob` writes a *fresh* full set of lesson rows
  tagged with a new UUID rather than updating existing rows in place. `LessonBuilderService` looks up the most
  recent `synchronization_id` for a course to know the "current" lesson set, and `LessonChangeDetector` diffs the
  old set against the newly-scraped one by a content signature (name/teacher/location/type/time/weekday) to decide
  whether anything actually changed before writing. Old synchronization batches are not pruned — if you build a
  feature against this table, filter by the latest `synchronization_id` per course rather than assuming one row
  per lesson slot.
- **`telegram_messages`**: existed in `V1__init_schema.sql` for a notification outbox but was dropped in
  `V3__remove_telegram_messages_table.sql` — there is currently no queued/retryable message-sending mechanism.
  Notifications, where they exist, are sent synchronously from the job/handler that triggers them.
- **`user_courses`**: the "tracked courses" join table the README's "User tracking" feature refers to. Read/written
  by `CourseService` (`getCoursesByDepartment` reads it to flag which courses a user tracks; `toggleTrackedCourse`
  adds/removes an entry). Nothing currently *consumes* the tracking to filter lesson-change notifications by
  user — `SynchronizeLessonsJob` still runs (and would notify, if notification sending existed) at the course
  level, not per-tracking-user.
- `ddl-auto` is `none` — schema changes only happen through new Flyway migrations (see
  [`guides/adding-a-db-migration.md`](guides/adding-a-db-migration.md)).

## Request flow: a Telegram update

1. `TelegramBotsLongPollingApplication` (registered in `TelegramBotConfig`) receives a batch of `Update`s from
   Telegram and hands it to `TelegramConsumer.consume(List<Update>)`.
2. `TelegramConsumer` dispatches each update onto a virtual thread (`Executors.newVirtualThreadPerTaskExecutor()`),
   chained per chat id through a `CompletableFuture` map so one chat's updates still process in order while
   different chats run concurrently — see "Concurrency: virtual threads" below. This overrides the library's
   default `consume(List<Update>)`, which otherwise serializes *all* chats through one shared background thread.
3. On its assigned virtual thread, `consume(Update)` walks `List<TelegramUpdateHandler>` — every `@Component`
   extending `TelegramUpdateHandler`, in Spring's injection order — calling `shouldHandle(update)` on each in
   turn, dispatching to (and stopping at) the first match.
4. The matched handler calls into one or more `service` classes (`ObisService`, `DailyMenuService`,
   `UserService`, `CourseService`, ...) and replies via the inherited `answerTextMessage` /
   `editTextMessage` helpers, or an `AnswerCallbackQuery` for callback-only acknowledgements
   (see `FoodMenuRatingHandler`).

Two ways state carries across messages, depending on shape:

- **Button-driven navigation** (faculty → department → course → lesson detail, food-menu ratings): encoded
  directly in the callback data as `"<CallbackData enum>:<id>"` and decoded with
  `CallbackDataByIdFilter`/`FoodMenuRatingCallbackDataFilter`. Stateless — the chat's current position lives in
  the button the user pressed, not in memory.
- **Free-text multi-step flows** (entering OBIS student number + password): tracked per-chat in an in-memory map
  (`ObisSessionManager` → `ObisSession`), because the next handler needs to interpret an arbitrary text message
  as "the answer to the question we just asked," which callback data can't express. This state is
  process-local and lost on restart — don't rely on it surviving a redeploy mid-flow.

## Concurrency: virtual threads

The app runs on Java 25 with two separate virtual-thread wirings, because neither the bot's update handling nor
the sync jobs are written reactively — both make blocking calls (`ObisClient`/`DailyMenuClient`/`TimetableClient`
all go through `RestClient`):

- **`spring.threads.virtual.enabled: true`** (`application.yml`) is Spring Boot's own switch: it puts the
  `@Scheduled` task executor (`SynchronizeLessonsJob`, `SynchronizeDailyMenusJob`) and the embedded Tomcat
  connector (pulled in by `spring-boot-starter-webmvc` for springdoc/Swagger) on virtual threads.
- **`TelegramConsumer`** does its own wiring, because the telegrambots library's default dispatch
  (`LongPollingSingleThreadUpdateConsumer.consume(List<Update>)`) funnels *every* chat through one shared
  background thread — meaning a single slow OBIS login would have stalled replies to every other chat.
  `TelegramConsumer` overrides that method: each update is submitted to
  `Executors.newVirtualThreadPerTaskExecutor()`, chained per chat id through a `Map<Long, CompletableFuture<Void>>`
  so a given chat's updates still run strictly in order (a double-tap on the same course-tracking button, or two
  quick messages in one OBIS credentials flow, must not race), while unrelated chats now process concurrently
  instead of queueing.

If you add new mutable per-chat/per-user state (the way `ObisSessionManager`/`ObisSession` and the
tracked-courses read-modify-write in `CourseService` already are), keep it keyed by chat/user id and don't assume
a single thread serializes access to it — that assumption is no longer true.

## Request flow: OBIS (student portal) access

OBIS (`obistest.manas.edu.kg`) has no API; the bot drives it like a browser would, per chat:

1. `ObisSessionManager.getSession(chatId)` returns (creating if absent) an `ObisSession` — a `RestClient` backed by
   a JDK `HttpClient` with its own `CookieManager`, which captures `Set-Cookie` headers and replays them as
   `Cookie` on every subsequent request (including redirects). One session per chat; sessions are never evicted.
2. `ObisService.authenticate` re-logs-in on *every* call that needs authenticated data: fetch the login page,
   scrape its CSRF token (`ObisParser.parseLoginPageCsrfToken`), then `ObisClient.sendLoginRequest`. The user's
   password is decrypted from `users.encrypted_password` (`CryptoService`, AES/ECB via `crypto.secret-key`) only
   for the duration of this call.
3. The now-authenticated session fetches the target page (`/vs-ders/taken-lessons`,
   `/vs-ders/taken-grades`) and `ObisParser` turns the HTML into `LessonAttendance`/`LessonExams` records.

Because every read re-authenticates, OBIS-backed handlers are inherently slower and more failure-prone than the
DB-backed timetable/menu handlers — expect and surface `ObisLoginException` / `ObisPageParserException` rather
than assuming success.

## Scraping + sync pattern (timetable, food menu)

Both scraped features follow the same three-stage shape, spread across the flat `client`/`parser`/`service`/`job`
packages; **use it for any new scraped data source** rather than having a job write straight from parsed data
into entities:

```
client (Jsoup/RestClient HTTP GET of a university HTML page)
   → parser (Jsoup: HTML → an immutable model record, no persistence knowledge)
      → job/service (compares parsed result against what's stored; writes only on real change)
```

- Timetable: `TimetableClient` (`client/`) → `TimetableParser`/`TimeRangeParser` (`parser/`) →
  `TimetableFetchService` (fetch) + `LessonBuilderService` (map to entities) + `LessonChangeDetector` (diff) +
  `LessonSynchronizeService` (orchestrates, `@Transactional`, one course at a time) — all in `service/` — +
  `SynchronizeLessonsJob` (`job/`, `@Scheduled(cron = "0 0 * * * *")`, hourly).
- Food menu: `DailyMenuClient` (`client/`) → `DailyMenuParser` (`parser/`) → `SynchronizeDailyMenusJob` (`job/`,
  `@Scheduled(fixedDelay = 10min)`) does fetch + diff (by normalized dish-name set per day) + write in one method,
  `@Transactional`.

Both intentionally avoid writing when nothing changed, to avoid needless `updated_at`/audit churn and (for
lessons) avoid spamming change notifications.

## Formatting layer

`service/*Formatter` classes (`CourseLessonFormatter`, `ExamsFormatter`, `AttendanceFormatter`,
`FoodMenuFormatter`) turn `model` records into the HTML-parse-mode Telegram message text. They're plain classes
with no Spring dependencies, which is why `CourseLessonFormatterTest` can instantiate `CourseLessonFormatter`
directly with `new` — keep new formatters dependency-free so they stay unit-testable the same way. Note the
existing formatter tests intentionally lock in some "current behavior" edge cases (e.g. a null field rendering as
the literal string `"null"`) — read a formatter test before changing its formatter, since some assertions encode
"don't change this by accident," not "this is the desired behavior."
