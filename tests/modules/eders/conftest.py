import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.eders.application.tracking import EdersTrackingService
from manashelper.modules.eders.infrastructure.repositories.eders import EdersRepository
from manashelper.modules.users.application.bot_status import BotStatusService
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from manashelper.platform.telegram.outbox.repository import OutboxRepository
from manashelper.platform.telegram.outbox.service import OutboxService


@pytest.fixture
def outbox(session: AsyncSession):
    return OutboxService(OutboxRepository(session), BotStatusService(UserRepository(session)))


@pytest.fixture
async def tracking(session: AsyncSession, outbox):
    session.add(User(id=980_001, full_name="Test", username=None))
    await session.flush()
    users = UserRepository(session)
    return EdersTrackingService(EdersRepository(session), UsersQuery(users), outbox)
