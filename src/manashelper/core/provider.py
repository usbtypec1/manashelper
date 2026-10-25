from collections.abc import AsyncGenerator, AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from manashelper.core.config import Settings, get_settings
from manashelper.core.database import create_engine, create_session_pool


class CoreProvider(Provider):
    scope = Scope.APP

    @provide
    def get_settings(self) -> Settings:
        return get_settings()

    @provide
    async def get_engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings)
        yield engine
        await engine.dispose()

    @provide
    def get_session_pool(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_pool(engine)

    @provide
    async def get_http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            yield http_client

    @provide(scope=Scope.REQUEST)
    async def get_session(
        self, session_pool: async_sessionmaker[AsyncSession]
    ) -> AsyncGenerator[AsyncSession, BaseException | None]:
        async with session_pool() as session:
            try:
                # Dishka sends the scope exception via asend(), rather than athrow().
                exception = yield session
                if exception is None:
                    await session.commit()
            except BaseException:
                await session.rollback()
                raise
            else:
                if exception is not None:
                    await session.rollback()
