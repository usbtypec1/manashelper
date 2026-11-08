from uuid import uuid4

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import text


async def test_dish_localization_preserves_original_data_indexes_and_references_on_round_trip(engine):
    migration = ScriptDirectory.from_config(Config("alembic.ini")).get_revision("V30").module
    schema = "dish_migration_" + uuid4().hex
    async with engine.connect() as connection, connection.begin():
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        await connection.execute(
            text("""CREATE TABLE food_dishes (
                id uuid PRIMARY KEY, name varchar(255) NOT NULL,
                photo_url varchar(255) NOT NULL, calories integer NOT NULL,
                created_at timestamp NOT NULL DEFAULT now()
            )""")
        )
        await connection.execute(text("CREATE UNIQUE INDEX ix_dishes_name ON food_dishes (name)"))
        await connection.execute(text("CREATE TABLE menu_dishes (dish_id uuid REFERENCES food_dishes(id))"))
        dish_id = uuid4()
        await connection.execute(
            text("INSERT INTO food_dishes (id, name, photo_url, calories) VALUES (:id, 'Çorba', 'original.jpg', 123)"),
            {"id": dish_id},
        )
        await connection.execute(text("INSERT INTO menu_dishes VALUES (:id)"), {"id": dish_id})
        original = (await connection.execute(text("SELECT to_jsonb(d) FROM food_dishes d"))).scalar_one()
        index_oid = await connection.scalar(text("SELECT 'ix_dishes_name'::regclass::oid"))

        def apply(sync_connection, operation):
            with Operations.context(MigrationContext.configure(sync_connection)):
                operation()

        for _ in range(2):
            await connection.run_sync(apply, migration.upgrade)
            row = (await connection.execute(text("SELECT to_jsonb(d) FROM food_dishes d"))).scalar_one()
            assert row == {
                **{key: value for key, value in original.items() if key != "name"},
                "name_tr": "Çorba",
                **dict.fromkeys(("name_en", "name_ru", "name_ky", "name_zh", "upscaled_photo_url")),
            }
            await connection.execute(text("UPDATE food_dishes SET name_ru = 'Суп', upscaled_photo_url = 'large.jpg'"))
            assert await connection.scalar(text("SELECT name_ru FROM food_dishes")) == "Суп"
            assert await connection.scalar(text("SELECT dish_id FROM menu_dishes")) == dish_id
            assert await connection.scalar(text("SELECT 'ix_dishes_name'::regclass::oid")) == index_oid
            await connection.run_sync(apply, migration.downgrade)
            assert (await connection.execute(text("SELECT to_jsonb(d) FROM food_dishes d"))).scalar_one() == original
            assert await connection.scalar(text("SELECT dish_id FROM menu_dishes")) == dish_id
            assert await connection.scalar(text("SELECT 'ix_dishes_name'::regclass::oid")) == index_oid
        await connection.rollback()
