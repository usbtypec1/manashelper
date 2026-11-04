import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import OutboxService
from tests.modules.eders.application_factories import build_eders_tracking_service
from tests.modules.users.application_factories import build_bot_status_service


@pytest.fixture
def outbox(session: AsyncSession):
    return OutboxService(OutboxRepository(session), build_bot_status_service(UserRepository(session)))


@pytest.fixture
async def tracking(session: AsyncSession, outbox):
    session.add(User(id=980_001, full_name="Test", username=None))
    await session.flush()
    users = UserRepository(session)
    return build_eders_tracking_service(EdersRepository(session), UsersQuery(users), outbox)
