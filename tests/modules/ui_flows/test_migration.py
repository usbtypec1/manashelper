import importlib.util
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema

from tests.paths import PROJECT_ROOT


async def test_migration_upgrade_and_downgrade_preserve_existing_user_data(engine):
    path = PROJECT_ROOT / "alembic/versions/84ba87e64380_add_ui_flow_versions_and_dialog_sessions.py"
    spec = importlib.util.spec_from_file_location("ui_flow_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    delivery_path = PROJECT_ROOT / "alembic/versions/f4e620d67ed7_add_ui_screen_delivery_intents.py"
    delivery_spec = importlib.util.spec_from_file_location("ui_delivery_migration", delivery_path)
    delivery_migration = importlib.util.module_from_spec(delivery_spec)
    delivery_spec.loader.exec_module(delivery_migration)
    auth_path = PROJECT_ROOT / "alembic/versions/1f3295d3d1ac_add_admin_login_tickets_and_web_sessions.py"
    auth_spec = importlib.util.spec_from_file_location("admin_auth_migration", auth_path)
    auth_migration = importlib.util.module_from_spec(auth_spec)
    auth_spec.loader.exec_module(auth_migration)
    location_path = PROJECT_ROOT / "alembic/versions/8e3edc9cfd80_add_user_locations_and_observed_.py"
    location_spec = importlib.util.spec_from_file_location("ui_location_migration", location_path)
    location_migration = importlib.util.module_from_spec(location_spec)
    location_spec.loader.exec_module(location_migration)
    return_path = PROJECT_ROOT / "alembic/versions/41edcfaadf86_track_returned_dialog_sessions.py"
    return_spec = importlib.util.spec_from_file_location("ui_return_migration", return_path)
    return_migration = importlib.util.module_from_spec(return_spec)
    return_spec.loader.exec_module(return_migration)
    rollout_path = PROJECT_ROOT / "alembic/versions/17f4cf2162e2_add_ui_flow_rollout_control.py"
    rollout_spec = importlib.util.spec_from_file_location("ui_rollout_migration", rollout_path)
    rollout_migration = importlib.util.module_from_spec(rollout_spec)
    rollout_spec.loader.exec_module(rollout_migration)
    schema = "ui_flow_migration_" + uuid4().hex
    # DDL and data are rolled back together; no downgrade is applied to the shared schema.
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(CreateSchema(schema))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.execute(text("CREATE TABLE users (id BIGINT PRIMARY KEY, full_name TEXT NOT NULL)"))
            await connection.execute(text("INSERT INTO users VALUES (1, 'preserve this user')"))

            def migrate(sync):
                with Operations.context(MigrationContext.configure(sync)):
                    migration.upgrade()
                    delivery_migration.upgrade()
                    auth_migration.upgrade()
                    session_id = uuid4()
                    sync.execute(text("INSERT INTO ui_flows (id,draft,draft_revision) VALUES ('seed','{}',0)"))
                    sync.execute(
                        text("""INSERT INTO ui_flow_versions
                        (flow_id,version,draft_revision,document,author_id) VALUES ('seed',1,0,'{}',1)""")
                    )
                    sync.execute(
                        text("""INSERT INTO ui_dialog_sessions
                        (id,user_id,chat_id,flow_id,flow_version,node_id,status,revision,data)
                        VALUES (:id,1,1,'seed',1,'step','waiting_input',0,'{"answer":"private-answer"}')"""),
                        {"id": session_id},
                    )
                    sync.execute(
                        text("""INSERT INTO ui_flow_events
                        (update_id,session_id,revision,kind,to_step,outcome)
                        VALUES (42,:id,0,'start','step','started')"""),
                        {"id": session_id},
                    )
                    location_migration.upgrade()
                    return_migration.upgrade()
                    rollout_migration.upgrade()
                    sync.execute(text("INSERT INTO ui_flow_rollout (id,mode,revision) VALUES (1,'off',1)"))
                    rollout_migration.downgrade()
                    assert sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions")) == "private-answer"
                    assert sync.scalar(text("SELECT result_session_id FROM ui_flow_events WHERE update_id=42")) is None
                    sync.execute(
                        text("UPDATE ui_flow_events SET result_session_id=:id WHERE update_id=42"), {"id": session_id}
                    )
                    return_migration.downgrade()
                    assert sync.scalar(text("SELECT count(*) FROM ui_flow_events")) == 1
                    assert sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions")) == "private-answer"
                    assert sync.scalar(text("SELECT owner FROM ui_user_locations WHERE user_id=1")) == "runtime"
                    assert sync.scalar(text("SELECT to_step FROM ui_user_transitions WHERE update_id=42")) == "step"
                    assert "private-answer" not in sync.scalar(
                        text("SELECT row_to_json(t)::text FROM ui_user_transitions t")
                    )
                    location_migration.downgrade()
                    assert sync.scalar(text("SELECT data->>'answer' FROM ui_dialog_sessions")) == "private-answer"
                    sync.execute(text("INSERT INTO admin_login_tickets VALUES ('ticket-hash', 1, now())"))
                    sync.execute(text("INSERT INTO admin_web_sessions VALUES ('session-hash', 1, now())"))
                    auth_migration.downgrade()
                    assert sync.scalar(text("SELECT count(*) FROM ui_screen_deliveries")) == 0
                    delivery_migration.downgrade()
                    assert sync.scalar(text("SELECT count(*) FROM ui_flows")) == 1
                    migration.downgrade()
                    assert sync.scalar(text("SELECT full_name FROM users WHERE id=1")) == "preserve this user"
                    migration.upgrade()
                    delivery_migration.upgrade()
                    auth_migration.upgrade()
                    location_migration.upgrade()
                    return_migration.upgrade()
                    rollout_migration.upgrade()

            await connection.run_sync(migrate)
        finally:
            await transaction.rollback()
