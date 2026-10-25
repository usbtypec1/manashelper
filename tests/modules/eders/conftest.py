import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.infrastructure.repository import EdersRepository
from manashelper.modules.users.infrastructure.user import User
from manashelper.modules.users.infrastructure.user_repository import UserRepository
from manashelper.modules.users.queries import UsersQuery


@pytest.fixture
async def tracking(session: AsyncSession):
    session.add(User(id=980_001, full_name="Test", username=None))
    await session.flush()
    return EdersTrackingService(EdersRepository(session), UsersQuery(UserRepository(session)))
