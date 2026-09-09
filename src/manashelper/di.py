from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from manashelper.config import Settings, get_settings
from manashelper.db.base import create_engine, create_session_pool
from manashelper.repositories.course_repository import CourseRepository
from manashelper.repositories.daily_menu_rating_repository import DailyMenuRatingRepository
from manashelper.repositories.daily_menu_repository import DailyMenuRepository
from manashelper.repositories.department_repository import DepartmentRepository
from manashelper.repositories.dish_repository import DishRepository
from manashelper.repositories.faculty_repository import FacultyRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.scraping.food_menu_client import FoodMenuClient
from manashelper.scraping.food_menu_parser import FoodMenuParser
from manashelper.scraping.obis_client import ObisClient
from manashelper.services.course_service import CourseService
from manashelper.services.crypto_service import CryptoService
from manashelper.services.daily_menu_service import DailyMenuService
from manashelper.services.department_service import DepartmentService
from manashelper.services.faculty_service import FacultyService
from manashelper.services.food_menu_sync_service import FoodMenuSyncService
from manashelper.services.obis_service import ObisService


class AppProvider(Provider):
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

    food_menu_client = provide(FoodMenuClient)
    food_menu_parser = provide(FoodMenuParser)
    crypto_service = provide(CryptoService)
    obis_client = provide(ObisClient)


class RequestProvider(Provider):
    scope = Scope.REQUEST

    @provide
    async def get_session(self, session_pool: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
        async with session_pool() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    faculty_repository = provide(FacultyRepository)
    department_repository = provide(DepartmentRepository)
    course_repository = provide(CourseRepository)
    user_repository = provide(UserRepository)
    dish_repository = provide(DishRepository)
    daily_menu_repository = provide(DailyMenuRepository)
    daily_menu_rating_repository = provide(DailyMenuRatingRepository)

    faculty_service = provide(FacultyService)
    department_service = provide(DepartmentService)
    course_service = provide(CourseService)
    daily_menu_service = provide(DailyMenuService)
    food_menu_sync_service = provide(FoodMenuSyncService)
    obis_service = provide(ObisService)
