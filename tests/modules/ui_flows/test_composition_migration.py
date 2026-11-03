import importlib.util
import json
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from tests.paths import PROJECT_ROOT


async def test_composition_migration_preserves_v1_documents_sessions_and_events(engine):
    path = PROJECT_ROOT / "alembic/versions/2cf16577afaf_add_pinned_scenario_dependencies_and_.py"
    spec = importlib.util.spec_from_file_location("composition_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "composition_migration_" + uuid4().hex
    original_id, old_writer_id, composed_id = uuid4(), uuid4(), uuid4()
    document = {
        "schema_version": 1,
        "id": "root",
        "entry": "answer",
        "fields": {"answer": {"type": "text"}},
        "nodes": [
            {
                "kind": "input",
                "id": "answer",
                "text": [{"kind": "catalog", "key": "survey.questions"}],
                "field": "answer",
                "input_type": "text",
                "next": "done",
                "error": {"kind": "catalog", "key": "common.error_retry"},
            },
            {"kind": "end", "id": "done", "status": "completed"},
        ],
    }
    original_data = {"answer": "preserve-private-answer", "attempt": 2}
    frame_data = {"answer": "caller-private-answer", "count": 2, "confirmed": True, "empty": None}
    frames = [{"flow_id": "root", "flow_version": 2, "node_id": "call", "data": frame_data}]
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.execute(
                text(
                    "CREATE TABLE ui_flow_versions (flow_id TEXT NOT NULL, version INTEGER NOT NULL, "
                    "document JSONB NOT NULL, PRIMARY KEY (flow_id, version))"
                )
            )
            await connection.execute(
                text(
                    "CREATE TABLE ui_dialog_sessions (id UUID PRIMARY KEY, flow_id TEXT NOT NULL, "
                    "flow_version INTEGER NOT NULL, node_id TEXT NOT NULL, revision INTEGER NOT NULL, "
                    "data JSONB NOT NULL, FOREIGN KEY (flow_id, flow_version) "
                    "REFERENCES ui_flow_versions(flow_id, version))"
                )
            )
            await connection.execute(
                text(
                    "CREATE TABLE ui_flow_events (update_id BIGINT PRIMARY KEY, "
                    "session_id UUID NOT NULL REFERENCES ui_dialog_sessions(id), revision INTEGER NOT NULL)"
                )
            )
            await connection.execute(
                text("INSERT INTO ui_flow_versions VALUES ('root', 1, CAST(:document AS JSONB))"),
                {"document": json.dumps(document)},
            )
            await connection.execute(
                text("INSERT INTO ui_dialog_sessions VALUES (:id, 'root', 1, 'answer', 7, CAST(:data AS JSONB))"),
                {"id": original_id, "data": json.dumps(original_data)},
            )
            await connection.execute(text("INSERT INTO ui_flow_events VALUES (510, :id, 7)"), {"id": original_id})

            def migrate(sync):
                def legacy_rows(table, added_column):
                    return list(
                        sync.scalars(
                            text(f"SELECT to_jsonb(record) - '{added_column}' FROM {table} AS record ORDER BY 1")
                        )
                    )

                with Operations.context(MigrationContext.configure(sync)):
                    migration.upgrade()
                    assert sync.scalar(text("SELECT dependencies FROM ui_flow_versions")) is None
                    assert sync.scalar(text("SELECT frames FROM ui_dialog_sessions")) is None
                    assert sync.scalar(text("SELECT document FROM ui_flow_versions")) == document
                    assert sync.scalar(text("SELECT data FROM ui_dialog_sessions")) == original_data

                    # Old binaries omit both nullable columns and can continue writing unchanged v1 records.
                    sync.execute(
                        text(
                            "INSERT INTO ui_flow_versions(flow_id,version,document) "
                            "VALUES ('root',2,CAST(:document AS JSONB))"
                        ),
                        {"document": json.dumps(document)},
                    )
                    sync.execute(
                        text(
                            "INSERT INTO ui_dialog_sessions(id,flow_id,flow_version,node_id,revision,data) "
                            "VALUES (:id,'root',1,'answer',0,'{}')"
                        ),
                        {"id": old_writer_id},
                    )
                    assert (
                        sync.scalar(text("SELECT frames FROM ui_dialog_sessions WHERE id=:id"), {"id": old_writer_id})
                        is None
                    )
                    assert sync.scalar(text("SELECT dependencies FROM ui_flow_versions WHERE version=2")) is None

                    sync.execute(
                        text("UPDATE ui_flow_versions SET dependencies=CAST(:dependencies AS JSONB) WHERE version=2"),
                        {"dependencies": json.dumps({"child": 1})},
                    )
                    sync.execute(
                        text(
                            "INSERT INTO ui_dialog_sessions(id,flow_id,flow_version,node_id,revision,data,frames) "
                            "VALUES (:id,'root',2,'answer',3,CAST(:data AS JSONB),CAST(:frames AS JSONB))"
                        ),
                        {
                            "id": composed_id,
                            "data": json.dumps({"answer": "child-value"}),
                            "frames": json.dumps(frames),
                        },
                    )
                    sync.execute(text("INSERT INTO ui_flow_events VALUES (511,:id,3)"), {"id": composed_id})
                    assert sync.scalar(text("SELECT dependencies FROM ui_flow_versions WHERE version=2")) == {
                        "child": 1
                    }
                    assert (
                        sync.scalar(text("SELECT frames FROM ui_dialog_sessions WHERE id=:id"), {"id": composed_id})
                        == frames
                    )
                    sessions = legacy_rows("ui_dialog_sessions", "frames")
                    versions = legacy_rows("ui_flow_versions", "dependencies")
                    events = legacy_rows("ui_flow_events", "unused")

                    migration.downgrade()
                    assert legacy_rows("ui_dialog_sessions", "frames") == sessions
                    assert legacy_rows("ui_flow_versions", "dependencies") == versions
                    assert legacy_rows("ui_flow_events", "unused") == events
                    assert not sync.scalar(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                            "WHERE table_schema=:schema AND "
                            "((table_name='ui_dialog_sessions' AND column_name='frames') "
                            "OR (table_name='ui_flow_versions' AND column_name='dependencies')))"
                        ),
                        {"schema": schema},
                    )

                    migration.upgrade()
                    assert legacy_rows("ui_dialog_sessions", "frames") == sessions
                    assert legacy_rows("ui_flow_versions", "dependencies") == versions
                    assert legacy_rows("ui_flow_events", "unused") == events
                    assert sync.scalar(text("SELECT count(*) FROM ui_dialog_sessions WHERE frames IS NOT NULL")) == 0
                    assert (
                        sync.scalar(text("SELECT count(*) FROM ui_flow_versions WHERE dependencies IS NOT NULL")) == 0
                    )

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()
