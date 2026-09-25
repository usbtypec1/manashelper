from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.broadcast import BroadcastService


async def test_get_recipient_ids_returns_every_user(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id=950_001, full_name="Test User", username=None),
            User(id=950_002, full_name="Test User", username=None),
        ]
    )
    await session.flush()

    service = BroadcastService(UserRepository(session))
    recipient_ids = await service.get_recipient_ids()

    assert {950_001, 950_002}.issubset(set(recipient_ids))
