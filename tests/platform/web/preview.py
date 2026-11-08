"""Synthetic PostgreSQL-backed Mini App fixture for local browser tests only."""

from datetime import UTC, datetime
from itertools import count
from uuid import uuid4

from aiogram import Bot, Dispatcher
from aiohttp import web
from dishka import Provider, Scope, make_async_container, provide
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from manashelper.bootstrap import load_models
from manashelper.core.config import get_settings
from manashelper.core.database import Base
from manashelper.core.provider import CoreProvider
from manashelper.modules.eders.provider import EdersProvider
from manashelper.modules.food_menu.provider import FoodMenuProvider
from manashelper.modules.gamification.infrastructure.repositories.achievement import AchievementRepository
from manashelper.modules.gamification.provider import GamificationProvider
from manashelper.modules.notifications.provider import NotificationsProvider
from manashelper.modules.obis.provider import ObisProvider
from manashelper.modules.schedule.infrastructure.models.course import Course
from manashelper.modules.schedule.infrastructure.models.department import Department
from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
from manashelper.modules.schedule.provider import ScheduleProvider
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.provider import UsersProvider
from manashelper.platform.telegram.outbox.provider import OutboxProvider
from manashelper.platform.web.server import create_web_app
from tests.platform.web.factories import TOKEN, authorization

PREVIEW_USER = 999_999_991_001


async def app() -> web.Application:
    load_models()
    bot = Bot(TOKEN)
    settings = get_settings().model_copy(
        update={"telegram_bot_token": TOKEN, "eders_password": SecretStr("fixture-eders-password")}
    )
    schema = "miniapp_preview_" + uuid4().hex
    admin_engine = create_async_engine(settings.database_url)
    async with admin_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    preview_engine = create_async_engine(
        settings.database_url, connect_args={"server_settings": {"search_path": schema}}
    )
    async with preview_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    class PreviewProvider(Provider):
        @provide(scope=Scope.APP, override=True)
        def engine(self) -> AsyncEngine:
            return preview_engine

    container = make_async_container(
        CoreProvider(),
        PreviewProvider(),
        UsersProvider(),
        GamificationProvider(),
        OutboxProvider(),
        NotificationsProvider(),
        ObisProvider(),
        EdersProvider(),
        ScheduleProvider(),
        FoodMenuProvider(),
    )
    application = create_web_app(bot, Dispatcher(), container, settings)
    preference_users = count(PREVIEW_USER + 1)

    async def fixture(request: web.Request) -> web.Response:
        user_id = PREVIEW_USER
        if request.query.get("preferences") == "1":
            user_id = next(preference_users)
            locale = request.query.get("locale", "ru")
            if locale not in {"en", "ru", "ky", "tr", "zh"}:
                raise web.HTTPBadRequest()
            async with container() as scope:
                session = await scope.get(AsyncSession)
                session.add(User(id=user_id, full_name="Preferences fixture", locale=locale))
        return web.json_response({"initData": authorization(user_id).removeprefix("tma ")})

    async def lifecycle(application: web.Application):
        async with container() as scope:
            session = await scope.get(AsyncSession)
            session.add(User(id=PREVIEW_USER, full_name="Студент <Manas>", locale="ru"))
            faculty = Faculty(id=uuid4(), name="Факультет <проверка>")
            department = Department(id=uuid4(), name="Информатика", faculty=faculty)
            session.add_all(
                [Course(id=1, number=1, department=department), Course(id=2, number=2, department=department)]
            )
            await session.flush()
            repo = await scope.get(AchievementRepository)
            await repo.set_enabled(PREVIEW_USER, True)
            progress = await repo.lock_progress(PREVIEW_USER)
            assert progress is not None
            progress.food_views = 63
            for key in ("foodie", "seller", "eldin_balasy"):
                await repo.award(PREVIEW_USER, key, datetime.now(UTC))
        try:
            yield
        finally:
            await container.close()
            await bot.session.close()
            await preview_engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin_engine.dispose()

    application.cleanup_ctx.append(lifecycle)
    application.router.add_get("/_fixture/init-data", fixture)
    return application


if __name__ == "__main__":
    web.run_app(app(), host="127.0.0.1", port=8765, access_log=None)
