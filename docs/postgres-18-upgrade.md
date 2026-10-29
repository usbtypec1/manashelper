# PostgreSQL 17 → 18

Dev Compose, production Compose and CI use `postgres:18-alpine`. PostgreSQL 18 stores
its cluster in `/var/lib/postgresql/18/docker`, so the volume mounts at `/var/lib/postgresql`.
The new `postgres18_data` volume is separate from `postgres_data`; the old cluster is
retained for rollback. Changing the image alone does not upgrade a PostgreSQL cluster.

## Existing installation

Schedule downtime and prevent writes until restoration and verification finish. These
commands are for the production Compose project in `/opt/manashelper`, with the same
`.env` credentials as PostgreSQL 17. For development, use `-f docker-compose.dev.yml`
on every Compose command and omit the `app` commands. Never run tests against production.

1. Before replacing the old Compose file, save it and record the current application
   image/version for rollback. Keep the same Compose project name throughout.
2. Stop the application and dump the still-running PostgreSQL 17 database. Store the
   archive outside the checkout in a protected directory; it contains private data:

   ```sh
   umask 077
   docker compose stop app
   docker compose exec -T db sh -ec \
     'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /secure-backups/manashelper-pg17.dump
   ```

   Check that `pg_dump` succeeds. Record exact row counts for the application's public
   tables and the `alembic_version` value for comparison after restoration.
3. Stop PostgreSQL 17, install the new Compose file, and start only PostgreSQL 18:

   ```sh
   docker compose stop db
   docker compose up -d --wait db
   docker compose exec -T db sh -ec \
     'pg_restore --exit-on-error --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
     < /secure-backups/manashelper-pg17.dump
   ```

   Restore into the fresh database before starting the app or applying new Alembic
   migrations. A failed restore rolls back the restore transaction; keep the app stopped
   and resolve the error. The commands assume the application's existing single database
   and owner role; custom additional roles/databases need their own backup and restore.
4. Verify `SHOW server_version`, `SHOW data_directory`, exact table row counts and the
   Alembic revision against the old database. Apply pending Alembic migrations and start
   the app using the normal release process. CI's deployment guard rejects an existing
   PG17 installation until its Compose `db` container has been replaced with PG18 by
   this manual procedure. New installations need no migration.

Keep the archive and old volume until the upgrade has been accepted. Do not run
`docker compose down -v` or delete either volume during the transition.

## Rollback

Before allowing new writes, stop `app` and `db`, restore the saved PostgreSQL 17 Compose
file and application version, then start `db` followed by `app`. The old `postgres_data`
volume still contains the original cluster. Leave `postgres18_data` intact for diagnosis.

Once writes resume on PostgreSQL 18, the old cluster is stale: switching volumes would
lose those writes. Keep the app stopped and plan a separate data reconciliation before
rolling back. Do not restore PostgreSQL 18 physical data into PostgreSQL 17.
