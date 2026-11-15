import runpy
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from tests.paths import PROJECT_ROOT


async def test_auth_state_upgrade_and_downgrade_preserve_existing_credentials_sessions_and_snapshots(session):
    schema = f"obis_migration_{uuid4().hex}"
    connection = await session.connection()

    def exercise(connection):
        # All DDL belongs to the fixture transaction and rolls back after the test.
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        connection.execute(text("CREATE TABLE users (id bigint PRIMARY KEY, encrypted_password text)"))
        connection.execute(text("CREATE TABLE obis_sessions (user_id bigint PRIMARY KEY, encrypted_cookies text)"))
        connection.execute(text("CREATE TABLE obis_snapshots (user_id bigint PRIMARY KEY, payload text)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'saved-password')"))
        connection.execute(text("INSERT INTO obis_sessions VALUES (1, 'saved-cookies')"))
        connection.execute(text("INSERT INTO obis_snapshots VALUES (1, 'saved-snapshot')"))
        migration = runpy.run_path(str(PROJECT_ROOT / "alembic/versions/V34_add_obis_auth_state.py"))
        with Operations.context(MigrationContext.configure(connection)):
            migration["upgrade"]()
            assert "obis_auth_states" in inspect(connection).get_table_names(schema=schema)
            connection.execute(
                text(
                    "INSERT INTO obis_auth_states "
                    "(user_id, manual_required, reason, failures, retry_at, notified) "
                    "VALUES (1, true, 'captcha', 0, NULL, false)"
                )
            )
            migration["downgrade"]()
        assert "obis_auth_states" not in inspect(connection).get_table_names(schema=schema)
        assert connection.execute(text("SELECT encrypted_password FROM users")).scalar_one() == "saved-password"
        assert connection.execute(text("SELECT encrypted_cookies FROM obis_sessions")).scalar_one() == "saved-cookies"
        assert connection.execute(text("SELECT payload FROM obis_snapshots")).scalar_one() == "saved-snapshot"

    await connection.run_sync(exercise)
