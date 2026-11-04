import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.modules.advertisements.application.advertisement import (
    AdvertisementNotFoundError,
)
from manashelper.modules.advertisements.application.use_cases.reveal_advertisement_contact import (
    RevealAdvertisementContactUseCase,
)
from manashelper.modules.advertisements.infrastructure.repositories.advertisement import AdvertisementRepository
from manashelper.modules.advertisements.infrastructure.repositories.advertisement_contact_view import (
    AdvertisementContactViewRepository,
)
from manashelper.modules.users.infrastructure.models.user import User
from manashelper.modules.users.infrastructure.repositories.user import UserRepository
from manashelper.modules.users.queries import UsersQuery
from tests.modules.advertisements.application_factories import (
    build_advertisement_moderation_service,
    build_advertisement_service,
)


async def _make_user(session: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, full_name="Test User", username="seller")
    session.add(user)
    await session.flush()
    return user


async def test_reveal_contact_for_published_ad_logs_view(session: AsyncSession) -> None:
    seller = await _make_user(session, 940_001)
    viewer = await _make_user(session, 940_003)

    ad_repository = AdvertisementRepository(session)
    ad_service = build_advertisement_service(ad_repository, UsersQuery(UserRepository(session)))
    summary = await ad_service.create_advertisement(
        user_id=seller.id,
        title="Item",
        description="Desc",
        price=None,
        expires_at=None,
        media_items=[],
        phone_number="+996700123456",
    )
    moderation_service = build_advertisement_moderation_service(ad_repository)
    await moderation_service.approve(summary.id)

    contact_service = RevealAdvertisementContactUseCase(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UsersQuery(UserRepository(session)),
    )
    reveal = await contact_service.execute(summary.id, viewer.id)

    assert reveal.advertisement_title == "Item"
    assert reveal.contact.username == "seller"


async def test_reveal_contact_raises_for_pending_ad(session: AsyncSession) -> None:
    seller = await _make_user(session, 940_004)
    viewer = await _make_user(session, 940_005)

    ad_repository = AdvertisementRepository(session)
    ad_service = build_advertisement_service(ad_repository, UsersQuery(UserRepository(session)))
    summary = await ad_service.create_advertisement(
        user_id=seller.id,
        title="Item",
        description="Desc",
        price=None,
        expires_at=None,
        media_items=[],
        phone_number="+996700123456",
    )

    contact_service = RevealAdvertisementContactUseCase(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UsersQuery(UserRepository(session)),
    )
    with pytest.raises(AdvertisementNotFoundError):
        await contact_service.execute(summary.id, viewer.id)


async def test_reveal_contact_raises_when_missing(session: AsyncSession) -> None:
    viewer = await _make_user(session, 940_006)

    ad_repository = AdvertisementRepository(session)
    contact_service = RevealAdvertisementContactUseCase(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UsersQuery(UserRepository(session)),
    )
    with pytest.raises(AdvertisementNotFoundError):
        await contact_service.execute(uuid.uuid4(), viewer.id)


async def test_each_advertisement_reveals_its_own_phone(session):
    seller = await _make_user(session, 940_101)
    viewer = await _make_user(session, 940_102)
    repository = AdvertisementRepository(session)
    service = build_advertisement_service(repository, UsersQuery(UserRepository(session)))
    contacts = RevealAdvertisementContactUseCase(
        repository, AdvertisementContactViewRepository(session), UsersQuery(UserRepository(session))
    )
    for phone in ["+996700111111", "+996700222222", None]:
        advertisement = await service.create_advertisement(
            seller.id, "Item", "Description", None, None, [], phone_number=phone
        )
        await build_advertisement_moderation_service(repository).approve(advertisement.id)
        reveal = await contacts.execute(advertisement.id, viewer.id)
        assert reveal.contact.phone_numbers == ([phone] if phone else [])
