import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from manashelper.core import config
from manashelper.core import provider as core_provider
from manashelper.core.config import Settings
from manashelper.core.provider import CoreProvider


@pytest.mark.parametrize("body_fails", [False, True])
async def test_engine_disposal_keeps_app_scope_and_closes_after_body_errors(monkeypatch, body_fails):
    engine = AsyncMock(spec=AsyncEngine)
    create_engine = Mock(return_value=engine)
    monkeypatch.setattr(core_provider, "create_engine", create_engine)
    container = make_async_container(CoreProvider())
    try:
        async with container:
            assert await container.get(AsyncEngine) is engine
            settings = await container.get(Settings)
            create_engine.assert_called_once_with(settings)
            async with container() as request:
                assert await request.get(AsyncEngine) is engine
                engine.dispose.assert_not_awaited()
            if body_fails:
                raise RuntimeError("App body failed")
    except RuntimeError as error:
        assert body_fails and str(error) == "App body failed"
    engine.dispose.assert_awaited_once_with()


async def test_http_client_keeps_app_scope_timeout_and_closes_with_container():
    async with make_async_container(CoreProvider()) as container:
        client = await container.get(httpx.AsyncClient)
        assert client.timeout == httpx.Timeout(15.0)
        assert not client.is_closed
        for _ in range(2):
            async with container() as request:
                assert await request.get(httpx.AsyncClient) is client
        assert not client.is_closed
    assert client.is_closed


async def test_core_session_factory_and_request_cache_work_without_feature_providers():
    async with make_async_container(CoreProvider()) as container:
        engine = await container.get(AsyncEngine)
        pool = await container.get(async_sessionmaker[AsyncSession])
        settings = await container.get(Settings)
        assert pool.kw["expire_on_commit"] is False and pool.kw["bind"] is engine
        async with container() as request:
            first = await request.get(AsyncSession)
            assert first is await request.get(AsyncSession)
            assert settings is await request.get(Settings)
            assert pool is await request.get(async_sessionmaker[AsyncSession])
        async with container() as request:
            assert first is not await request.get(AsyncSession)
            assert engine is await request.get(AsyncEngine)


async def test_core_request_session_commits_before_closing():
    session = AsyncMock(spec=AsyncSession)
    session.__aenter__.return_value = session
    events = []
    session.commit.side_effect = lambda: events.append("commit")
    session.__aexit__.side_effect = lambda *args: events.append("close")
    pool = Mock(return_value=session)

    class SessionPool(Provider):
        @provide(scope=Scope.APP, override=True)
        def session_pool(self) -> async_sessionmaker[AsyncSession]:
            return pool

    async with make_async_container(CoreProvider(), SessionPool()) as container:
        async with container() as request:
            assert await request.get(AsyncSession) is session
            assert events == []
        assert events == ["commit", "close"]
        session.rollback.assert_not_awaited()


def test_settings_keep_cwd_dotenv_aliases_overrides_and_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    values = {
        "TELEGRAM_BOT_TOKEN": "123456:development-placeholder",
        "DATASOURCE_NAME": "development",
        "DATASOURCE_USERNAME": "student",
        "DATASOURCE_PASSWORD": "placeholder",
        "OBIS_ENCRYPTION_KEY": "placeholder",
        "ADVERTISEMENT_CHANNEL_ID": "-1000000000000",
        "ADVERTISEMENT_CHANNEL_LINK": "https://t.me/example",
        "MODERATION_CHAT_ID": "-1000000000001",
        "ADMIN_CHAT_ID": "-1000000000002",
    }
    for key in (*values, "DATASOURCE_HOST", "EDERS_POLL_MINUTES"):
        monkeypatch.delenv(key, raising=False)
    Path(".env").write_text("\n".join(f"{key}={value}" for key, value in values.items()))
    config.get_settings.cache_clear()
    try:
        settings = config.get_settings()
        assert settings.datasource_host == "db" and settings.eders_poll_minutes == 30
        assert settings.database_url == "postgresql+asyncpg://student:placeholder@db:5432/development"
        monkeypatch.setenv("DATASOURCE_HOST", "localhost")
        assert config.get_settings() is settings
        config.get_settings.cache_clear()
        assert config.get_settings().datasource_host == "localhost"
    finally:
        config.get_settings.cache_clear()


def test_logging_keeps_cwd_path_utf8_rotation_and_replaces_handlers(tmp_path):
    # Isolate root-logger changes from pytest's logging capture.
    script = dedent("""\
        import logging
        from logging.handlers import RotatingFileHandler
        from pathlib import Path
        from manashelper.core.logging import configure_logging
        configure_logging()
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO and len(root.handlers) == 2
        files = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(files) == 1
        handler = files[0]
        assert handler.maxBytes == 50 * 1024 * 1024 and handler.backupCount == 2
        assert Path(handler.baseFilename) == Path('logs/manashelper.log').resolve()
        logging.getLogger('core-proof').info('Проверка логирования')
        handler.flush()
        text = Path('logs/manashelper.log').read_text(encoding='utf-8')
        assert 'INFO core-proof: Проверка логирования' in text
    """)
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
