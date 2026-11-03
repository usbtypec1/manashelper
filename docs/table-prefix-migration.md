# Feature table names

Revision `ce84a19d7032` renames 13 tables. It does not change columns, indexes,
constraints or stored data. PostgreSQL keeps foreign keys attached to the same
tables; ORM foreign-key targets use the new names. Existing index and constraint
names are deliberately retained.

| Previous name | Current name |
| --- | --- |
| `advertisements` | `advertisement_ads` |
| `user_exam_grades` | `obis_user_exam_grades` |
| `user_lesson_attendance` | `obis_user_lesson_attendance` |
| `daily_menus` | `food_daily_menus` |
| `dishes` | `food_dishes` |
| `daily_menu_dishes` | `food_daily_menu_dishes` |
| `daily_menu_ratings` | `food_daily_menu_ratings` |
| `faculties` | `timetable_faculties` |
| `departments` | `timetable_departments` |
| `courses` | `timetable_courses` |
| `lessons` | `timetable_lessons` |
| `lesson_history` | `timetable_lesson_history` |
| `user_courses` | `timetable_user_courses` |

Other feature tables already have the requested prefixes. Shared `users` and
`notification_settings` remain unchanged, including the OBIS credential columns.
The student survey and its ORM mapping have been removed. Subsequent revision
`df29b7418a60` drops `student_questions_responses` together with its answers.
All other tables and their data remain unchanged.

Revision `e5170c4b92a8` removes scheduled message deletion, its five-minute job and
food-menu auto-delete controls. It drops `scheduled_message_deletions` and
`food_menu_cleanup_settings`; downgrading recreates their empty schemas.

Revision `f62b3a09cd71` moves saved phone numbers into
`advertisement_ads.phone_numbers` (JSONB), then drops `user_phone_numbers`. Every
existing advertisement receives all its author's saved numbers, in their previous
order. New advertisements ask for one number each; only authors with a current
Telegram username can skip it. Profile phone settings are removed.

The contact migration downgrade restores distinct numbers from remaining ads into
the profile table. Original phone-row IDs/timestamps and numbers belonging to users
without any advertisements cannot be recovered. It then removes the new column.

## Applying and rolling back

Table renames require a coordinated application cutover: old and new application
versions cannot use the same database concurrently. Stop the bot and its jobs,
apply `uv run alembic upgrade head`, then start the new version. Application
startup also applies pending migrations.

To roll back, stop the new application, run
`uv run alembic downgrade ba2d4708e921` using the new checkout, then start the
previous application version. Table renames retain the data in both directions.
The survey table downgrade recreates its empty schema; it does not recover deleted
answers. PostgreSQL runs these migrations transactionally, so a failed migration
rolls back its changes.
