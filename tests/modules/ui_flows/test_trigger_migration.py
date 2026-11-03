import importlib.util
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema

from tests.paths import PROJECT_ROOT


async def test_trigger_migration_preserves_old_sessions_and_immutable_releases(engine):
    path = PROJECT_ROOT / "alembic/versions/2deed60a5bfd_versioned_ui_triggers_and_ingress_.py"
    spec = importlib.util.spec_from_file_location("trigger_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "trigger_migration_" + uuid4().hex
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.execute(
                text("CREATE TABLE ui_dialog_sessions (id INTEGER PRIMARY KEY, data JSONB NOT NULL)")
            )
            await connection.execute(
                text('INSERT INTO ui_dialog_sessions VALUES (1,\'{"answer":"preserve-private-answer"}\')')
            )

            def migrate(sync):
                with Operations.context(MigrationContext.configure(sync)):
                    migration.upgrade()
                    assert sync.scalar(text("SELECT trigger_release FROM ui_dialog_sessions WHERE id=1")) is None
                    with pytest.raises(DBAPIError), sync.begin_nested():
                        sync.execute(
                            text("INSERT INTO ui_trigger_state(id,revision,draft,current_release) VALUES(1,0,'{}',999)")
                        )
                    sync.execute(
                        text(
                            "INSERT INTO ui_trigger_releases (id,draft_revision,manifest,author_id) "
                            "VALUES (1,0,'{}',10)"
                        )
                    )
                    for query in (
                        "UPDATE ui_trigger_releases SET draft_revision=9 WHERE id=1",
                        "DELETE FROM ui_trigger_releases WHERE id=1",
                    ):
                        with pytest.raises(DBAPIError), sync.begin_nested():
                            sync.execute(text(query))
                    sync.execute(text("INSERT INTO ui_dialog_sessions(id,data) VALUES (2,'{}')"))
                    assert sync.scalar(text("SELECT trigger_release FROM ui_dialog_sessions WHERE id=2")) is None
                    migration.downgrade()
                    assert (
                        sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions WHERE id=1"))
                        == "preserve-private-answer"
                    )
                    migration.upgrade()
                    assert sync.scalar(text("SELECT count(*) FROM ui_dialog_sessions")) == 2

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()
