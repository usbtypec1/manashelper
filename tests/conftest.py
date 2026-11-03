from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from manashelper.bootstrap import load_models
from manashelper.core.config import get_settings

load_models()


@pytest.fixture(scope="session")
def baseline_texts():
    from manashelper.platform.i18n.seed import import_document
    from ui_flows.domain.texts import TextSnapshot

    return TextSnapshot(1, import_document())


@pytest.fixture(autouse=True)
def text_context(baseline_texts):
    """Pure formatter tests bind an explicit import snapshot, never a runtime file fallback."""
    from manashelper.platform.i18n.catalog import i18n

    with i18n.use_catalog(baseline_texts):
        yield


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(get_settings().database_url)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to a transaction that is rolled back after the test.

    Uses ``join_transaction_mode="create_savepoint"`` so that even if the code under
    test calls ``session.commit()``, it only releases a SAVEPOINT — the outer
    transaction (and thus every change made during the test) is discarded on rollback.
    """
    async with engine.connect() as connection:
        await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as test_session:
            yield test_session
        await connection.rollback()


@pytest_asyncio.fixture
async def catalog_pool(engine, baseline_texts):
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.schema import CreateSchema, DropSchema

    from common.database import Base
    from manashelper.platform.i18n.repository import initialize_catalog

    name = "text_catalog_test_" + uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(name))
    scoped_engine = engine.execution_options(schema_translate_map={None: name})
    try:
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        pool = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with pool.begin() as session:
            await initialize_catalog(session, baseline_texts.document)
        yield pool
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(name, cascade=True))
