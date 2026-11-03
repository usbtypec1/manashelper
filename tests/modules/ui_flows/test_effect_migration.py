import importlib.util
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
async def predecessor(engine):
    path = PROJECT_ROOT / "alembic/versions/fd0178000ef5_add_durable_external_operations_and_.py"
    spec = importlib.util.spec_from_file_location("effect_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    schema = "effect_migration_" + uuid4().hex
    original = uuid4()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            for statement in (
                "CREATE TABLE ui_dialog_sessions (id UUID PRIMARY KEY, chat_id BIGINT NOT NULL, "
                "status TEXT NOT NULL, data JSONB NOT NULL, revision INTEGER NOT NULL, "
                "CONSTRAINT ck_ui_dialog_status CHECK "
                "(status IN ('running','waiting_button','waiting_input',"
                "'completed','cancelled','handed_off','failed')))",
                "CREATE UNIQUE INDEX uq_ui_dialog_active_chat ON ui_dialog_sessions(chat_id) "
                "WHERE status IN ('running','waiting_button','waiting_input')",
                "CREATE TABLE ui_flow_events (update_id BIGINT PRIMARY KEY, "
                "session_id UUID NOT NULL REFERENCES ui_dialog_sessions(id), kind TEXT NOT NULL)",
                "CREATE TABLE ui_screen_deliveries (token TEXT PRIMARY KEY, update_id BIGINT NOT NULL UNIQUE "
                "REFERENCES ui_flow_events(update_id), screen JSONB NOT NULL)",
                "CREATE TABLE ui_user_locations (user_id BIGINT PRIMARY KEY, update_id BIGINT NOT NULL, "
                "owner TEXT NOT NULL)",
                "CREATE TABLE ui_user_transitions (id BIGINT PRIMARY KEY, update_id BIGINT NOT NULL, "
                "outcome TEXT NOT NULL)",
            ):
                await connection.execute(text(statement))
            await connection.execute(
                text("INSERT INTO ui_dialog_sessions VALUES (:id,991401,'waiting_input','{\"answer\":\"keep\"}',7)"),
                {"id": original},
            )
            await connection.execute(text("INSERT INTO ui_flow_events VALUES (600,:id,'input')"), {"id": original})
            await connection.execute(text("INSERT INTO ui_screen_deliveries VALUES ('legacy-screen',600,'{}')"))
            await connection.execute(text("INSERT INTO ui_user_locations VALUES (991401,600,'runtime')"))
            await connection.execute(text("INSERT INTO ui_user_transitions VALUES (1,600,'advanced')"))
            yield connection, migration, original, schema
        finally:
            await transaction.rollback()


def rows(connection, table, *, legacy=False):
    expression = "to_jsonb(record) - 'operation_id' - 'message_ids'" if legacy else "to_jsonb(record)"
    return list(connection.scalars(text(f"SELECT {expression} FROM {table} AS record ORDER BY 1")))


def operation(connection, session_id, operation_id=None):
    operation_id = operation_id or uuid4()
    connection.execute(
        text(
            "INSERT INTO ui_external_operations "
            "(id,session_id,user_id,chat_id,revision,flow_id,flow_version,node_id,delegate_id,"
            "contract_version,arguments,status) "
            "VALUES (:operation,:session,991401,991401,7,'example',1,'verify','example.verify',1,'{}','pending')"
        ),
        {"operation": operation_id, "session": session_id},
    )
    return operation_id


async def test_effect_upgrade_enforces_waiting_slot_receipt_origins_and_foreign_keys(predecessor):
    connection, migration, original, schema = predecessor

    def verify(sync):
        with Operations.context(MigrationContext.configure(sync)):
            migration.upgrade()
            sync.execute(text("UPDATE ui_dialog_sessions SET status='waiting_effect' WHERE id=:id"), {"id": original})
            with pytest.raises(DBAPIError), sync.begin_nested():
                sync.execute(
                    text("INSERT INTO ui_dialog_sessions VALUES (:id,991401,'waiting_input','{}',0)"),
                    {"id": uuid4()},
                )
            with pytest.raises(DBAPIError), sync.begin_nested():
                operation(sync, uuid4())
            work = operation(sync, original)
            with pytest.raises(DBAPIError), sync.begin_nested():
                operation(sync, original)
            with pytest.raises(DBAPIError), sync.begin_nested():
                sync.execute(
                    text(
                        "INSERT INTO ui_input_secrets VALUES "
                        "(:id,:session,991401,991401,'opaque',now()+interval '1 minute')"
                    ),
                    {"id": uuid4(), "session": uuid4()},
                )
            for update_id, operation_id in ((None, None), (600, work), (None, uuid4())):
                with pytest.raises(DBAPIError), sync.begin_nested():
                    sync.execute(
                        text("INSERT INTO ui_screen_deliveries VALUES (:token,:update,'{}',:operation)"),
                        {"token": str(uuid4()), "update": update_id, "operation": operation_id},
                    )
            sync.execute(
                text("INSERT INTO ui_screen_deliveries VALUES ('effect-screen',NULL,'{}',:operation)"),
                {"operation": work},
            )
            with pytest.raises(DBAPIError), sync.begin_nested():
                sync.execute(
                    text("INSERT INTO ui_screen_deliveries VALUES ('duplicate-effect',NULL,'{}',:operation)"),
                    {"operation": work},
                )
            assert (
                sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions WHERE id=:id"), {"id": original})
                == "keep"
            )
            for table in ("ui_user_locations", "ui_user_transitions"):
                with pytest.raises(DBAPIError), sync.begin_nested():
                    sync.execute(text(f"UPDATE {table} SET operation_id=:operation"), {"operation": uuid4()})
            sync.execute(text("DELETE FROM ui_external_operations WHERE id=:id"), {"id": work})
            assert sync.scalar(text("SELECT count(*) FROM ui_screen_deliveries")) == 1
            sync.execute(text("UPDATE ui_dialog_sessions SET status='waiting_input' WHERE id=:id"), {"id": original})
            before = {
                table: rows(sync, table, legacy=True)
                for table in (
                    "ui_dialog_sessions",
                    "ui_flow_events",
                    "ui_screen_deliveries",
                    "ui_user_locations",
                    "ui_user_transitions",
                )
            }
            migration.downgrade()
            for table, expected in before.items():
                assert rows(sync, table, legacy=True) == expected
            for table in ("ui_external_operations", "ui_input_secrets"):
                assert sync.scalar(text("SELECT to_regclass(:table)"), {"table": f"{schema}.{table}"}) is None
            migration.upgrade()
            for table, expected in before.items():
                assert rows(sync, table, legacy=True) == expected
            assert (
                sync.scalar(
                    text(
                        "SELECT is_nullable FROM information_schema.columns WHERE table_schema=:schema "
                        "AND table_name='ui_screen_deliveries' AND column_name='update_id'"
                    ),
                    {"schema": schema},
                )
                == "YES"
            )

    await connection.run_sync(verify)


@pytest.mark.parametrize("new_state", ["waiting", "operation", "secret", "delivery", "location", "transition"])
async def test_effect_downgrade_refuses_new_work_and_history_before_changing_schema(predecessor, new_state):
    connection, migration, original, _ = predecessor

    def verify(sync):
        with Operations.context(MigrationContext.configure(sync)):
            migration.upgrade()
            if new_state == "waiting":
                sync.execute(text("UPDATE ui_dialog_sessions SET status='waiting_effect'"))
            elif new_state in {"operation", "delivery"}:
                work = operation(sync, original)
                if new_state == "delivery":
                    sync.execute(
                        text("INSERT INTO ui_screen_deliveries VALUES ('new-origin',NULL,'{}',:operation)"),
                        {"operation": work},
                    )
            elif new_state == "secret":
                sync.execute(
                    text(
                        "INSERT INTO ui_input_secrets VALUES "
                        "(:id,:session,991401,991401,'opaque',now()+interval '1 minute')"
                    ),
                    {"id": uuid4(), "session": original},
                )
            else:
                table = "ui_user_locations" if new_state == "location" else "ui_user_transitions"
                sync.execute(text(f"UPDATE {table} SET update_id=NULL"))
            tables = (
                "ui_dialog_sessions",
                "ui_external_operations",
                "ui_input_secrets",
                "ui_screen_deliveries",
                "ui_user_locations",
                "ui_user_transitions",
            )
            before = {table: rows(sync, table) for table in tables}
            with pytest.raises(DBAPIError, match="Cannot downgrade durable effects"), sync.begin_nested():
                migration.downgrade()
            for table, expected in before.items():
                assert rows(sync, table) == expected
            assert (
                sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions WHERE id=:id"), {"id": original})
                == "keep"
            )

    await connection.run_sync(verify)
