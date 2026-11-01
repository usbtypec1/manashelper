import json
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from common.database import Base
from manashelper.modules.ui_flows.catalog import get_catalog_texts
from manashelper.modules.users.infrastructure.user import User
from manashelper.platform.i18n.catalog import i18n
from tests.paths import FIXTURES_DIR
from ui_flows.application.validation import validate_flow
from ui_flows.domain.contracts import DelegateDefinition
from ui_flows.domain.schema import DataField, FlowDocument

FEATURES = {
    "food_menu",
    "marketplace",
    "settings",
    "schedule",
    "study_week",
    "attendance",
    "grades",
    "eders",
    "eders_materials",
}


@pytest.fixture
def main_menu_document():
    return json.loads((FIXTURES_DIR / "ui_flows/main_menu.json").read_text(encoding="utf-8"))


@pytest.fixture
def survey_document():
    return json.loads((FIXTURES_DIR / "ui_flows/student_questions.json").read_text(encoding="utf-8"))


@pytest.fixture
def validate_document():
    definitions = json.loads((FIXTURES_DIR / "ui_flows/delegates.json").read_text(encoding="utf-8"))
    delegates = [DelegateDefinition.model_validate(item) for item in definitions]
    with i18n.context(), i18n.use_locale("en"):
        keys = set(get_catalog_texts())

    def validate(document):
        return validate_flow(
            FlowDocument.model_validate(document),
            delegates=delegates,
            features=FEATURES,
            catalog_keys=keys,
            capabilities={"eders_enabled": DataField(type="boolean")},
        )

    return validate


@pytest_asyncio.fixture
async def flow_user(session):
    user = User(id=991_401, full_name="UI flow test", username=None)
    session.add(user)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def isolated_flow_pool(engine):
    """Committed concurrency tests live in their own disposable PostgreSQL schema."""
    name = "ui_flow_test_" + uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(CreateSchema(name))
    scoped_engine = engine.execution_options(schema_translate_map={None: name})
    try:
        async with scoped_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(scoped_engine, expire_on_commit=False)
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(name, cascade=True))


@pytest_asyncio.fixture
async def session(isolated_flow_pool):
    """UI-flow IDs are stable; keep tests independent of authored documents in the development DB."""
    async with isolated_flow_pool.kw["bind"].connect() as connection:
        await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as test_session:
            yield test_session
        await connection.rollback()


@pytest_asyncio.fixture
async def telegram_flow(isolated_flow_pool, monkeypatch):
    from aiogram import Bot

    from manashelper.core.config import get_settings
    from tests.modules.ui_flows.telegram_factory import TelegramHarness, container_for, dispatcher_for

    admin = 991_450
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(admin))
    get_settings.cache_clear()
    bot = Bot(token="123456:development-placeholder")
    try:
        async with container_for(isolated_flow_pool) as container:
            harness = TelegramHarness(bot, dispatcher_for(container, admin), admin)
            monkeypatch.setattr(bot.session, "make_request", harness.respond)
            yield harness, container, isolated_flow_pool
    finally:
        await bot.session.close()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def admin_api(isolated_flow_pool, monkeypatch, tmp_path):
    import httpx

    from manashelper.admin_main import create_app
    from manashelper.core.config import get_settings
    from tests.modules.ui_flows.admin_factory import AdminHarness, admin_container

    user_id = 991_460
    monkeypatch.setenv("MANASHELPER_ADMIN_CHAT_ID", str(user_id))
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_ORIGIN", "https://admin.test")
    monkeypatch.setenv("MANASHELPER_ADMIN_WEB_SIGNING_KEY", "synthetic-admin-signing-key-only-for-tests")
    get_settings.cache_clear()
    async with isolated_flow_pool.begin() as session:
        session.add(User(id=user_id, full_name="API admin", locale="en"))
    try:
        async with admin_container(isolated_flow_pool) as container:
            app = create_app(get_settings(), container, ui_directory=tmp_path / "unbuilt")
            async with (
                app.router.lifespan_context(app),
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
                    base_url="https://admin.test",
                    headers={"Origin": "https://admin.test"},
                ) as client,
            ):
                yield AdminHarness(client, container, isolated_flow_pool, app, user_id)
    finally:
        get_settings.cache_clear()
