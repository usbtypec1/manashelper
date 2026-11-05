import importlib.util
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from tests.paths import PROJECT_ROOT


def load_migration(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / "alembic" / "versions" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_access_migration_defaults_off_and_preserves_existing_data_on_round_trip(engine):
    original = load_migration("V28_add_gamification_and_webhook_receipts")
    migration = load_migration("V29_add_gamification_access_and_progress")
    schema = "achievement_migration_" + uuid4().hex
    # All schema/data changes are rolled back, including creation of this private schema.
    async with engine.connect() as connection, connection.begin():
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        await connection.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY)"))

        def apply(sync_connection, operation):
            with Operations.context(MigrationContext.configure(sync_connection)):
                operation()

        await connection.run_sync(apply, original.upgrade)
        await connection.execute(text("INSERT INTO users VALUES (1), (2)"))
        await connection.execute(text("INSERT INTO gamification_progress (user_id, food_views) VALUES (1, 49)"))
        await connection.execute(
            text(
                "INSERT INTO gamification_achievements (user_id, achievement_key, earned_at) "
                "VALUES (1, 'seller', '2026-11-01T00:00:00Z')"
            )
        )
        await connection.run_sync(apply, migration.upgrade)
        await connection.execute(text("INSERT INTO gamification_progress (user_id) VALUES (2)"))
        rows = (
            await connection.execute(
                text(
                    "SELECT user_id, enabled, food_views, aa_count, attendance_count "
                    "FROM gamification_progress ORDER BY user_id"
                )
            )
        ).all()
        assert rows == [(1, False, 49, 0, 0), (2, False, 0, 0, 0)]
        await connection.execute(text("UPDATE gamification_progress SET enabled = true WHERE user_id = 1"))
        await connection.run_sync(apply, migration.downgrade)
        assert await connection.scalar(text("SELECT food_views FROM gamification_progress WHERE user_id = 1")) == 49
        assert await connection.scalar(text("SELECT count(*) FROM gamification_achievements")) == 1
        await connection.run_sync(apply, migration.upgrade)
        assert await connection.scalar(text("SELECT enabled FROM gamification_progress WHERE user_id = 1")) is False
        assert await connection.scalar(text("SELECT count(*) FROM gamification_achievements")) == 1
        await connection.rollback()
