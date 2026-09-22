import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.user_contact import UserContactService, UserNotFoundError


async def test_get_contact_status_reflects_username(session: AsyncSession) -> None:
    user = User(id=930_001, full_name="Test User", username="testuser")
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    status = await service.get_contact_status(user.id)

    assert status.username == "testuser"
    assert status.phone_numbers == []
    assert status.has_contact is True


async def test_get_contact_status_with_no_contact(session: AsyncSession) -> None:
    user = User(id=930_002, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    status = await service.get_contact_status(user.id)

    assert status.has_contact is False


async def test_add_phone_number_deduplicates(session: AsyncSession) -> None:
    user = User(id=930_003, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    await service.add_phone_number(user.id, "+996700000000")
    status = await service.add_phone_number(user.id, "+996700000000")

    assert status.phone_numbers == ["+996700000000"]
    assert status.has_contact is True


async def test_get_contact_status_raises_when_user_missing(session: AsyncSession) -> None:
    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    with pytest.raises(UserNotFoundError):
        await service.get_contact_status(999_999)
