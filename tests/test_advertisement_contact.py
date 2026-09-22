import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.advertisement_contact_view_repository import AdvertisementContactViewRepository
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.repositories.user_phone_number_repository import UserPhoneNumberRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.advertisement import AdvertisementNotFoundError, AdvertisementService
from manashelper.services.advertisement_contact import AdvertisementContactService
from manashelper.services.advertisement_moderation import AdvertisementModerationService
from manashelper.services.user_contact import UserContactService


async def _make_user(session: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, full_name="Test User", username="seller")
    session.add(user)
    await session.flush()
    return user


async def test_reveal_contact_for_published_ad_logs_view(session: AsyncSession) -> None:
    seller = await _make_user(session, 940_001)
    viewer = await _make_user(session, 940_003)

    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=seller.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )
    moderation_service = AdvertisementModerationService(ad_repository)
    await moderation_service.approve(summary.id)

    contact_service = AdvertisementContactService(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UserContactService(UserRepository(session), UserPhoneNumberRepository(session)),
    )
    reveal = await contact_service.reveal_contact(summary.id, viewer.id)

    assert reveal.advertisement_title == "Item"
    assert reveal.contact.username == "seller"


async def test_reveal_contact_raises_for_pending_ad(session: AsyncSession) -> None:
    seller = await _make_user(session, 940_004)
    viewer = await _make_user(session, 940_005)

    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=seller.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    contact_service = AdvertisementContactService(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UserContactService(UserRepository(session), UserPhoneNumberRepository(session)),
    )
    with pytest.raises(AdvertisementNotFoundError):
        await contact_service.reveal_contact(summary.id, viewer.id)


async def test_reveal_contact_raises_when_missing(session: AsyncSession) -> None:
    viewer = await _make_user(session, 940_006)

    ad_repository = AdvertisementRepository(session)
    contact_service = AdvertisementContactService(
        ad_repository,
        AdvertisementContactViewRepository(session),
        UserContactService(UserRepository(session), UserPhoneNumberRepository(session)),
    )
    with pytest.raises(AdvertisementNotFoundError):
        await contact_service.reveal_contact(uuid.uuid4(), viewer.id)
