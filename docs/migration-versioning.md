# Migration versioning

Migration filenames use sequential version numbers:

```text
V1_init_schema.py
V2_seed_faculties_departments_courses.py
```

Create a migration from the repository root:

```sh
uv run python scripts/new_migration.py --autogenerate -m "add example"
```

For a handwritten migration, omit `--autogenerate`. The helper forwards standard
Alembic revision flags and selects one more than the largest existing V-number.
The first new revision after the 25 historical migrations is `V26`.

If parallel branches choose the same number, resolve the conflict before either
migration is applied. Never renumber an already applied revision. Alembic still
orders migrations by parent links and requires merging multiple heads.

## Existing databases

Files `V1` through `V25` follow the existing revision chain. Their contents,
historical `revision` and `down_revision` values remain unchanged. New migrations
use the V-number as both their revision ID and filename prefix.

Alembic finds the revision recorded in the database by its internal ID, regardless
of the filename. Production databases keep recognizing every existing revision.
No database rewrite, `stamp`, rollback or reapplication is needed for this rename.
Normal `uv run alembic current`, `history` and `upgrade head` commands still work.
