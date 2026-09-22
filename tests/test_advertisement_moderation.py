import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.services.advertisement import AdvertisementService
from manashelper.services.advertisement_moderation import AdvertisementModerationService, AdvertisementNotPendingError


async def _make_user(session: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, full_name="Test User", username=None)
    session.add(user)
    await session.flush()
    return user


async def test_approve_publishes_advertisement(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_001)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository)
    approved = await moderation_service.approve(summary.id)

    assert approved.status.value == "published"


async def test_approve_twice_raises_not_pending(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_002)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository)
    await moderation_service.approve(summary.id)

    with pytest.raises(AdvertisementNotPendingError):
        await moderation_service.approve(summary.id)


async def test_reject_stores_comment(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_003)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository)
    rejected = await moderation_service.reject(summary.id, "Not allowed")

    assert rejected.status.value == "rejected"
    assert rejected.rejection_comment == "Not allowed"


async def test_reject_twice_raises_not_pending(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_004)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository)
    await moderation_service.reject(summary.id, None)

    with pytest.raises(AdvertisementNotPendingError):
        await moderation_service.reject(summary.id, None)
