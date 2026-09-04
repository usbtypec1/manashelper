# Guide: adding a new scraped data source

Background: [`../ARCHITECTURE.md`](../ARCHITECTURE.md#scraping--sync-pattern-timetable-food-menu) describes the
client → parser → job pipeline used by the timetable and food-menu sync flows. This guide walks through adding a
new one, using those two as the reference implementations.

## 1. Drop each piece into its layer package

There are no per-feature subpackages — a new scraped data source doesn't get its own folder. Its pieces land
directly in the existing flat packages, named for the feature (e.g. `ExamScheduleClient`, `ExamScheduleParser`):
the client in `client/`, the parser in `parser/`, any new entity in `entity/`, its repository in `repository/`,
its model records in `model/`, its mapper (if any) in `mapper/`, and the sync job in `job/`.

## 2. Client: fetch raw HTML

A `client` class's only job is an HTTP call that returns the page as a `String`. Look at `DailyMenuClient` /
`TimetableClient` (both in `client/`) for the shape — plain Jsoup or `RestClient` GET, no parsing, no persistence.
Keep any auth/session concerns (cookies, CSRF) out of here unless the source needs them, in which case mirror the
`ObisSession`/`ObisSessionManager` pattern (in `service/`) rather than inventing a new one.

## 3. Parser: HTML → an immutable model record

A `parser` class takes the raw HTML string and returns a `model` (a `record`, not an entity) with no
Spring/JPA dependencies — see `DailyMenuParser` and `TimetableParser` (both in `parser/`). This separation is
what makes parsers unit testable without a database or Spring context. Keep parsing defensive: university sites
format their HTML by hand, so tolerate missing/reordered fields rather than assuming exact structure — throw a
specific exception (pattern: `*NotFoundException`/`*ParserException`, in the top-level `exception/` package) when
the page shape is unrecognizable, rather than letting a `NullPointerException`/`IndexOutOfBoundsException` bubble
up unlabeled.

## 4. Diff before writing

Do not write parsed data straight into entities on every run — both existing jobs compare against what's stored
and skip the write when nothing changed:

- `SynchronizeDailyMenusJob` normalizes dish names into a `Set<String>` and compares old vs. new per day; a match
  means it `continue`s without touching the DB.
- `LessonChangeDetector` builds a content signature per lesson (name/teacher/location/type/time/weekday) and
  diffs the stored set against the newly-scraped set to compute `TimetableLessonChanges` (added/removed), which
  `LessonSynchronizeService` only persists when `hasChanges(...)` is true.

Pick whichever comparison shape fits your data (a name/id set, or a full content signature) but keep the "skip if
identical" behavior — it avoids needless write churn, spurious `updated_at`/audit changes, and (if you add
notifications) spamming users for non-changes.

## 5. Schedule it

Add a `@Scheduled` method in a `job` class (or reuse an existing job's service if the sync logic belongs there).
Pick an interval proportional to how often the source actually changes — the existing jobs use `cron = "0 0 * * * *"`
(hourly, timetable) and `fixedDelay = 10, timeUnit = TimeUnit.MINUTES` (food menu). Wrap the sync method in
`@Transactional` if it does multiple related writes that should commit atomically, as both existing jobs do.

## 6. Migration first, entity second

Add the Flyway migration for any new tables/columns before writing the JPA entity —
see [`adding-a-db-migration.md`](adding-a-db-migration.md). `ddl-auto` is `none`; Hibernate will not create
anything for you.
