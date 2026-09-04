# Guide: adding a database migration

Background: [`../ARCHITECTURE.md`](../ARCHITECTURE.md#data-model) — Flyway owns the schema; JPA `ddl-auto` is
`none` (`manashelper-bot/src/main/resources/application.yml`), so nothing here is optional or auto-generated at
startup.

## Rules

- Migrations live in `manashelper-bot/src/main/resources/db/migration/`, named
  `V<next-number>__<snake_case_description>.sql`
  (see `V1__init_schema.sql` ... `V4__remove_daily_menu_ratings_comment_column.sql`). Numbers are sequential and
  never reused or reordered — always add a new `V<N+1>` file, never edit a migration that has already been
  committed/released.
- One logical change per migration (one new table, one column drop, one constraint change) — mirrors the existing
  history, e.g. `V3` removes exactly one table, `V4` drops exactly one column.
- `FlywayConfig` runs with `baselineOnMigrate(true)`, so an existing non-Flyway-tracked database is baselined at
  the current version rather than replayed from `V1` — don't rely on `V1` running against a live environment.
- IDs are `UUID` (`GenerationType.UUID`, generated application-side) for most entities, plain `BIGINT`/`INTEGER`
  for `users`/`courses` (external ids from the university systems, not generated). Match whichever pattern the
  table you're touching already uses.
- Add indexes for new foreign keys and any column you'll filter/sort by at scale — see
  `idx_lessons_course_id`/`idx_lessons_time` as the pattern for a lookup + a range-query index on the same table.

## After adding the migration

1. Update (or add) the JPA `@Entity` to match — `nullable`, `length`, and column names must mirror the migration
   exactly, since Hibernate does not validate or generate DDL here.
2. If the entity is exposed through a mapper (`*Mapper` in the top-level `mapper/` package — hand-written entity
   ↔ model conversion; MapStruct is on the classpath but not actually used by any current mapper), add the new
   field there too.
3. Run `mvn clean verify` (or `mvn clean verify -pl manashelper-bot`) and start the app locally against a fresh
   dev database (`docker-compose.dev.yml`) to
   confirm Flyway applies the migration cleanly — the current test suite (`CourseLessonFormatterTest`) is a plain
   unit test with no Spring context, so it will not catch a broken migration or entity/schema mismatch.
