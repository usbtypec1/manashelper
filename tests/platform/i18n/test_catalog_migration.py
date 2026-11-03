import importlib.util
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema

from tests.paths import PROJECT_ROOT


async def test_catalog_migration_preserves_old_documents_answers_and_writer_compatibility(engine):
    path = PROJECT_ROOT / "alembic/versions/d91e6b1a7f23_versioned_text_catalog.py"
    spec = importlib.util.spec_from_file_location("text_catalog_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "text_migration_" + uuid4().hex
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.execute(
                text("CREATE TABLE ui_flow_versions (version INTEGER PRIMARY KEY,document JSONB NOT NULL)")
            )
            await connection.execute(text("INSERT INTO ui_flow_versions VALUES (1,'{\"nodes\":[]}')"))
            await connection.execute(
                text("CREATE TABLE ui_dialog_sessions (id INTEGER PRIMARY KEY,data JSONB NOT NULL)")
            )
            await connection.execute(
                text('INSERT INTO ui_dialog_sessions VALUES (1,\'{"answer":"preserve-private-answer"}\')')
            )

            def migrate(sync):
                with Operations.context(MigrationContext.configure(sync)):
                    migration.upgrade()
                    assert sync.scalar(text("SELECT text_catalog_release FROM ui_flow_versions WHERE version=1")) == 1
                    assert (
                        sync.scalar(
                            text("SELECT jsonb_array_length(document->'entries') FROM text_catalog_releases WHERE id=1")
                        )
                        == 356
                    )
                    sync.execute(text("INSERT INTO ui_flow_versions(version,document) VALUES(2,'{}')"))
                    assert (
                        sync.scalar(text("SELECT text_catalog_release FROM ui_flow_versions WHERE version=2")) is None
                    )
                    for query in (
                        "UPDATE text_catalog_releases SET draft_revision=9 WHERE id=1",
                        "DELETE FROM text_catalog_releases WHERE id=1",
                    ):
                        with pytest.raises(DBAPIError), sync.begin_nested():
                            sync.execute(text(query))
                    migration.downgrade()
                    assert (
                        sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions WHERE id=1"))
                        == "preserve-private-answer"
                    )
                    assert (
                        sync.scalar(text("SELECT document::text FROM ui_flow_versions WHERE version=1"))
                        == '{"nodes": []}'
                    )
                    migration.upgrade()
                    assert sync.scalar(text("SELECT count(*) FROM ui_flow_versions")) == 2

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()
