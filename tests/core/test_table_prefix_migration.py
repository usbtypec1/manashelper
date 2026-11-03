"""Exercise real migration history in a disposable PostgreSQL schema."""

from datetime import UTC, date, datetime
from uuid import uuid4

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, MetaData, String, Uuid, inspect, select, text

from manashelper.core.database import Base


def _seed_tables(connection, metadata):
    rows = {}
    for table in metadata.sorted_tables:
        values = {}
        for column in table.columns:
            if column.foreign_keys:
                target = next(iter(column.foreign_keys)).column
                values[column.name] = rows[target.table.name][target.name]
            elif column.server_default is not None or column.nullable:
                continue
            elif isinstance(column.type, Uuid):
                values[column.name] = uuid4()
            elif isinstance(column.type, Boolean):
                values[column.name] = True
            elif isinstance(column.type, Integer):
                values[column.name] = 987601 if column.primary_key else 1
            elif isinstance(column.type, Float):
                values[column.name] = 12.5
            elif isinstance(column.type, DateTime):
                values[column.name] = datetime.now(UTC) if column.type.timezone else datetime.now()
            elif isinstance(column.type, Date):
                values[column.name] = date(2026, 11, 3)
            elif isinstance(column.type, String):
                values[column.name] = "x"
            else:
                raise AssertionError(f"Unhandled column type: {table.name}.{column.name}: {column.type}")
        if table.name == "users":
            values.update(student_number="123456", encrypted_password="preserved-ciphertext", locale="ru")
        elif table.name == "user_phone_numbers":
            values["phone_number"] = "+996 (700) 11-22-33"
        rows[table.name] = (
            connection.execute(table.insert().values(**values).returning(*table.columns)).mappings().one()
        )


def _snapshot(connection):
    result = {}
    for name in inspect(connection).get_table_names():
        oid = connection.scalar(text("SELECT CAST(CAST(:name AS regclass) AS oid)"), {"name": name})
        columns = connection.execute(
            text("""
                SELECT a.attnum, a.attname, a.atttypid, a.atttypmod, a.attnotnull,
                       a.attidentity, a.attgenerated, pg_get_expr(d.adbin, d.adrelid)
                FROM pg_attribute a
                LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
                WHERE a.attrelid = :oid AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum
            """),
            {"oid": oid},
        ).all()
        constraints = connection.execute(
            text("""
                SELECT oid, conname, contype, conkey, confrelid, confkey,
                       confupdtype, confdeltype, confmatchtype, condeferrable, condeferred, convalidated
                FROM pg_constraint WHERE conrelid = :oid ORDER BY oid
            """),
            {"oid": oid},
        ).all()
        indexes = connection.execute(
            text("""
                SELECT i.indexrelid, c.relname, i.indisunique, i.indisprimary, i.indkey,
                       i.indclass, i.indoption, i.indexprs::text, i.indpred::text
                FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
                WHERE i.indrelid = :oid ORDER BY i.indexrelid
            """),
            {"oid": oid},
        ).all()
        rows = (
            connection.exec_driver_sql(f'SELECT to_jsonb(t) FROM "{name}" t ORDER BY to_jsonb(t)::text').scalars().all()
        )
        result[name] = (oid, columns, constraints, indexes, rows)
    return result


def _verify_migration(connection):
    historical_tables = set(Base.metadata.tables) - {"telegram_outbox", "telegram_outbox_rate_buckets"}
    schema = f"table_prefix_test_{uuid4().hex}"
    connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    revision = scripts.get_revision("ce84a19d7032")
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        for previous in reversed(list(scripts.walk_revisions(base="base", head=revision.down_revision))):
            previous.module.upgrade()

        metadata = MetaData()
        metadata.reflect(connection)
        _seed_tables(connection, metadata)
        connection.execute(
            metadata.tables["user_phone_numbers"]
            .insert()
            .values(
                id=uuid4(),
                user_id=connection.scalar(select(metadata.tables["users"].c.id)),
                phone_number="0700223344",
                created_at=datetime(2027, 1, 1),
            )
        )
        before = _snapshot(connection)
        renames = dict(revision.module.TABLE_RENAMES)
        assert set(renames) <= before.keys()
        assert all(value[-1] for value in before.values()), "Every historical table must contain data"

        revision.module.upgrade()
        after = _snapshot(connection)
        assert after == {renames.get(name, name): value for name, value in before.items()}
        survey_table = "student_questions_responses"
        cleanup_tables = {"scheduled_message_deletions", "food_menu_cleanup_settings"}
        assert set(after) == historical_tables | {survey_table, "user_phone_numbers"} | cleanup_tables

        revision.module.downgrade()
        assert _snapshot(connection) == before
        revision.module.upgrade()
        assert _snapshot(connection) == after

        removal = scripts.get_revision("df29b7418a60")
        removal.module.upgrade()
        remaining = {name: value for name, value in after.items() if name != survey_table}
        assert _snapshot(connection) == remaining
        assert set(remaining) == historical_tables | cleanup_tables | {"user_phone_numbers"}

        removal.module.downgrade()
        restored = _snapshot(connection)
        assert restored.pop(survey_table)[1] == after[survey_table][1]
        assert restored == remaining
        assert connection.exec_driver_sql(f'SELECT count(*) FROM "{survey_table}"').scalar_one() == 0

        removal.module.upgrade()
        assert _snapshot(connection) == remaining

        cleanup_removal = scripts.get_revision("e5170c4b92a8")
        cleanup_removal.module.upgrade()
        final = {name: value for name, value in remaining.items() if name not in cleanup_tables}
        assert _snapshot(connection) == final
        assert set(final) == historical_tables | {"user_phone_numbers"}

        cleanup_removal.module.downgrade()
        restored = _snapshot(connection)
        for name in cleanup_tables:
            recreated = restored.pop(name)
            assert recreated[1] == remaining[name][1]
            assert recreated[-1] == []
        assert restored == final

        cleanup_removal.module.upgrade()
        assert _snapshot(connection) == final

        contact_migration = scripts.get_revision("f62b3a09cd71")
        old_phones = final["user_phone_numbers"][-1]
        contact_migration.module.upgrade()
        current = _snapshot(connection)
        assert set(current) == historical_tables
        for name in set(final) - {"advertisement_ads", "user_phone_numbers"}:
            assert current[name] == final[name]
        old_ad = final["advertisement_ads"]
        new_ad = current["advertisement_ads"]
        assert new_ad[0] == old_ad[0]
        assert new_ad[1][:-1] == old_ad[1]
        old_constraint_ids = {constraint[0] for constraint in old_ad[2]}
        assert [constraint for constraint in new_ad[2] if constraint[0] in old_constraint_ids] == old_ad[2]
        added_constraints = [constraint for constraint in new_ad[2] if constraint[0] not in old_constraint_ids]
        assert all(constraint[2] == b"n" and constraint[3] == [new_ad[1][-1][0]] for constraint in added_constraints)
        assert new_ad[3] == old_ad[3]
        for row in new_ad[-1]:
            expected = [
                phone["phone_number"]
                for phone in sorted(old_phones, key=lambda phone: (phone["created_at"], phone["id"]))
                if phone["user_id"] == row["user_id"]
            ]
            original = next(old for old in old_ad[-1] if old["id"] == row["id"])
            assert row == {**original, "phone_numbers": expected}

        # Apply later additions before executing current ORM mappings, then prove
        # their downgrade preserves the data under this historical migration.
        later_revisions = [scripts.get_revision(name) for name in ("V26", "V27")]
        for later in later_revisions:
            later.module.upgrade()
        after = _snapshot(connection)
        # Execute current ORM mappings, including all renamed foreign-key joins.
        for table in Base.metadata.sorted_tables:
            count = len(after[table.name][-1])
            assert len(connection.execute(select(table)).all()) == count
            for foreign_key in table.foreign_keys:
                parent = foreign_key.column.table
                if parent is not table:
                    assert (
                        len(
                            connection.execute(
                                select(table).join(parent, foreign_key.parent == foreign_key.column)
                            ).all()
                        )
                        == count
                    )

        for later in reversed(later_revisions):
            later.module.downgrade()
        assert _snapshot(connection) == current
        contact_migration.module.downgrade()
        reverted = _snapshot(connection)
        assert reverted["advertisement_ads"] == final["advertisement_ads"]
        assert {(row["user_id"], row["phone_number"]) for row in reverted["user_phone_numbers"][-1]} == {
            (row["user_id"], row["phone_number"]) for row in old_phones
        }
        contact_migration.module.upgrade()
        reapplied = _snapshot(connection)
        assert [
            {**row, "phone_numbers": sorted(row["phone_numbers"])} for row in reapplied["advertisement_ads"][-1]
        ] == [{**row, "phone_numbers": sorted(row["phone_numbers"])} for row in current["advertisement_ads"][-1]]
        assert {name: value for name, value in reapplied.items() if name != "advertisement_ads"} == {
            name: value for name, value in current.items() if name != "advertisement_ads"
        }


async def test_prefix_and_survey_removal_migrations_preserve_other_tables_and_support_rollback(engine):
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.run_sync(_verify_migration)
        finally:
            await transaction.rollback()
