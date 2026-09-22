import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.db.models.user import UserRole
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.repositories.user_repository import UserRepository
from manashelper.services.advertisement import AdvertisementService
from manashelper.services.advertisement_moderation import (
    AdvertisementModerationService,
    AdvertisementNotPendingError,
    ModeratorForbiddenError,
)


async def _make_user(session: AsyncSession, user_id: int, role: UserRole = UserRole.USER) -> User:
    user = User(id=user_id, full_name="Test User", username=None, role=role.value)
    session.add(user)
    await session.flush()
    return user


async def test_approve_publishes_advertisement(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_001)
    moderator = await _make_user(session, 920_002, role=UserRole.MARKETPLACE_ADMIN)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository, UserRepository(session))
    approved = await moderation_service.approve(summary.id, moderator.id)

    assert approved.status.value == "published"


async def test_approve_raises_for_non_moderator(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_003)
    non_moderator = await _make_user(session, 920_004)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository, UserRepository(session))
    with pytest.raises(ModeratorForbiddenError):
        await moderation_service.approve(summary.id, non_moderator.id)


async def test_approve_twice_raises_not_pending(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_005)
    moderator = await _make_user(session, 920_006, role=UserRole.SUPERADMIN)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository, UserRepository(session))
    await moderation_service.approve(summary.id, moderator.id)

    with pytest.raises(AdvertisementNotPendingError):
        await moderation_service.approve(summary.id, moderator.id)


async def test_reject_stores_comment(session: AsyncSession) -> None:
    owner = await _make_user(session, 920_007)
    moderator = await _make_user(session, 920_008, role=UserRole.MARKETPLACE_ADMIN)
    ad_repository = AdvertisementRepository(session)
    ad_service = AdvertisementService(ad_repository)
    summary = await ad_service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    moderation_service = AdvertisementModerationService(ad_repository, UserRepository(session))
    rejected = await moderation_service.reject(summary.id, moderator.id, "Not allowed")

    assert rejected.status.value == "rejected"
    assert rejected.rejection_comment == "Not allowed"


async def test_get_moderator_ids_returns_admin_roles(session: AsyncSession) -> None:
    await _make_user(session, 920_009, role=UserRole.USER)
    admin = await _make_user(session, 920_010, role=UserRole.MARKETPLACE_ADMIN)
    superadmin = await _make_user(session, 920_011, role=UserRole.SUPERADMIN)

    moderation_service = AdvertisementModerationService(AdvertisementRepository(session), UserRepository(session))
    moderator_ids = set(await moderation_service.get_moderator_ids())

    assert admin.id in moderator_ids
    assert superadmin.id in moderator_ids
