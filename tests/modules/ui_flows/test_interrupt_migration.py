import importlib.util
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema

from tests.paths import PROJECT_ROOT


@pytest_asyncio.fixture
async def interrupt_predecessor(engine):
    path = PROJECT_ROOT / "alembic/versions/a7572f78b034_preserve_external_effect_correlation_.py"
    spec = importlib.util.spec_from_file_location("interrupt_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "interrupt_migration_" + uuid4().hex
    legacy, called = uuid4(), uuid4()
    frame = {"flow_id": "parent", "flow_version": 1, "node_id": "call", "data": {"answer": "keep parent"}}
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.execute(
                text(
                    "CREATE TABLE ui_dialog_sessions (id UUID PRIMARY KEY, status TEXT NOT NULL, "
                    "revision INTEGER NOT NULL, data JSONB NOT NULL, frames JSONB)"
                )
            )
            await connection.execute(
                text("INSERT INTO ui_dialog_sessions VALUES (:id,'waiting_input',3,'{\"answer\":\"keep v1\"}',NULL)"),
                {"id": legacy},
            )
            await connection.execute(
                text(
                    "INSERT INTO ui_dialog_sessions VALUES "
                    "(:id,'waiting_input',7,'{\"answer\":\"keep child\"}',CAST(:frames AS JSONB))"
                ),
                {"id": called, "frames": json.dumps([frame])},
            )
            yield connection, migration, schema, legacy, called
        finally:
            await transaction.rollback()


def payloads(connection):
    return list(
        connection.scalars(
            text("SELECT to_jsonb(session) - 'effect_revision' FROM ui_dialog_sessions AS session ORDER BY id")
        )
    )


async def test_upgrade_preserves_v1_and_normal_frames_accepts_old_writers_and_safe_roundtrip(interrupt_predecessor):
    connection, migration, schema, legacy, called = interrupt_predecessor

    def verify(sync):
        before = payloads(sync)
        with Operations.context(MigrationContext.configure(sync)):
            migration.upgrade()
            assert payloads(sync) == before
            assert list(sync.scalars(text("SELECT effect_revision FROM ui_dialog_sessions"))) == [None, None]
            assert (
                sync.scalar(
                    text(
                        "SELECT is_nullable FROM information_schema.columns WHERE table_schema=:schema "
                        "AND table_name='ui_dialog_sessions' AND column_name='effect_revision'"
                    ),
                    {"schema": schema},
                )
                == "YES"
            )
            old_writer = uuid4()
            sync.execute(
                text(
                    "INSERT INTO ui_dialog_sessions (id,status,revision,data,frames) "
                    "VALUES (:id,'waiting_input',0,'{}','[]')"
                ),
                {"id": old_writer},
            )
            assert (
                sync.scalar(text("SELECT effect_revision FROM ui_dialog_sessions WHERE id=:id"), {"id": old_writer})
                is None
            )
            with pytest.raises(DBAPIError), sync.begin_nested():
                sync.execute(text("UPDATE ui_dialog_sessions SET effect_revision=-1 WHERE id=:id"), {"id": called})
            before = payloads(sync)
            migration.downgrade()
            assert payloads(sync) == before
            assert (
                sync.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
                        "AND table_name='ui_dialog_sessions' AND column_name='effect_revision'"
                    ),
                    {"schema": schema},
                )
                == 0
            )
            migration.upgrade()
            assert payloads(sync) == before
            assert (
                sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions WHERE id=:id"), {"id": legacy})
                == "keep v1"
            )
            assert (
                sync.scalar(
                    text("SELECT frames->0->'data'->>'answer' FROM ui_dialog_sessions WHERE id=:id"), {"id": called}
                )
                == "keep parent"
            )

    await connection.run_sync(verify)


@pytest.mark.parametrize("new_state", ["effect_revision", "interrupt_frame", "null_resume_status"])
async def test_downgrade_refuses_interrupt_payload_before_ddl_and_preserves_all_data(interrupt_predecessor, new_state):
    connection, migration, schema, _, called = interrupt_predecessor

    def verify(sync):
        with Operations.context(MigrationContext.configure(sync)):
            migration.upgrade()
            if new_state == "effect_revision":
                sync.execute(text("UPDATE ui_dialog_sessions SET effect_revision=0 WHERE id=:id"), {"id": called})
            else:
                status = "waiting_input" if new_state == "interrupt_frame" else None
                frames = [
                    {
                        "flow_id": "suspended",
                        "flow_version": 1,
                        "node_id": "answer",
                        "data": {"answer": "private retained"},
                        "resume_status": status,
                        "revision": 7,
                        "effect_revision": None,
                        "trigger_release": None,
                    }
                ]
                sync.execute(
                    text("UPDATE ui_dialog_sessions SET frames=CAST(:frames AS JSONB) WHERE id=:id"),
                    {"id": called, "frames": json.dumps(frames)},
                )
            before = list(sync.scalars(text("SELECT to_jsonb(session) FROM ui_dialog_sessions AS session ORDER BY id")))
            with pytest.raises(RuntimeError, match="durable interrupt continuations"), sync.begin_nested():
                migration.downgrade()
            assert (
                list(sync.scalars(text("SELECT to_jsonb(session) FROM ui_dialog_sessions AS session ORDER BY id")))
                == before
            )
            assert (
                sync.scalar(
                    text(
                        "SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema "
                        "AND table_name='ui_dialog_sessions' AND column_name='effect_revision'"
                    ),
                    {"schema": schema},
                )
                == 1
            )
            assert (
                sync.scalar(
                    text(
                        "SELECT count(*) FROM pg_constraint WHERE conrelid='ui_dialog_sessions'::regclass "
                        "AND conname='ck_ui_dialog_effect_revision'"
                    )
                )
                == 1
            )

    await connection.run_sync(verify)
