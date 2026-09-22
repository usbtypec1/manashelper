import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.user_contact import (
    InvalidPhoneNumberError,
    PhoneNumberForbiddenError,
    PhoneNumberNotFoundError,
    UserContactService,
    UserNotFoundError,
)


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


async def test_add_phone_number_rejects_invalid_input(session: AsyncSession) -> None:
    user = User(id=930_004, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    with pytest.raises(InvalidPhoneNumberError):
        await service.add_phone_number(user.id, "not a phone number")


async def test_delete_phone_number_removes_it(session: AsyncSession) -> None:
    user = User(id=930_005, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    await service.add_phone_number(user.id, "+996700000001")
    [phone_number] = await service.get_phone_numbers(user.id)

    await service.delete_phone_number(user.id, phone_number.id)

    assert await service.get_phone_numbers(user.id) == []


async def test_delete_phone_number_raises_for_other_user(session: AsyncSession) -> None:
    owner = User(id=930_006, full_name="Test User", username=None)
    other = User(id=930_007, full_name="Test User", username=None)
    session.add_all([owner, other])
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    await service.add_phone_number(owner.id, "+996700000002")
    [phone_number] = await service.get_phone_numbers(owner.id)

    with pytest.raises(PhoneNumberForbiddenError):
        await service.delete_phone_number(other.id, phone_number.id)


async def test_delete_phone_number_raises_when_missing(session: AsyncSession) -> None:
    user = User(id=930_008, full_name="Test User", username=None)
    session.add(user)
    await session.flush()

    service = UserContactService(UserRepository(session), UserPhoneNumberRepository(session))
    with pytest.raises(PhoneNumberNotFoundError):
        await service.delete_phone_number(user.id, uuid.uuid4())
