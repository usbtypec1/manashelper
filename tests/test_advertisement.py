import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.db.models.advertisement import Advertisement
from manashelper.db.models.advertisement_media import AdvertisementMediaType
from manashelper.repositories.advertisement_repository import AdvertisementRepository
from manashelper.services.advertisement import (
    AdvertisementForbiddenError,
    AdvertisementMediaItem,
    AdvertisementNotFoundError,
    AdvertisementService,
    TooManyAdvertisementsError,
)


async def _make_user(session: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, full_name="Test User", username=None)
    session.add(user)
    await session.flush()
    return user


async def test_create_advertisement_with_media(session: AsyncSession) -> None:
    user = await _make_user(session, 910_001)
    service = AdvertisementService(AdvertisementRepository(session))

    summary = await service.create_advertisement(
        user_id=user.id,
        title="Bike",
        description="A nice bike",
        price=1000,
        expires_at=None,
        media_items=[AdvertisementMediaItem(file_id="file1", media_type=AdvertisementMediaType.PHOTO)],
    )

    assert summary.title == "Bike"
    assert summary.price == 1000
    assert len(summary.media) == 1
    assert summary.media[0].file_id == "file1"


async def test_create_advertisement_raises_after_five_in_an_hour(session: AsyncSession) -> None:
    user = await _make_user(session, 910_002)
    service = AdvertisementService(AdvertisementRepository(session))

    for _ in range(5):
        await service.create_advertisement(
            user_id=user.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
        )

    with pytest.raises(TooManyAdvertisementsError):
        await service.create_advertisement(
            user_id=user.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
        )


async def test_get_page_by_user_id_paginates(session: AsyncSession) -> None:
    user = await _make_user(session, 910_003)
    repository = AdvertisementRepository(session)
    for index in range(12):
        repository.add(Advertisement(id=uuid.uuid4(), user_id=user.id, title=f"Item {index}", description="Desc"))
    await session.flush()

    service = AdvertisementService(repository)
    page0 = await service.get_page_by_user_id(user.id, 0)
    page1 = await service.get_page_by_user_id(user.id, 1)

    assert len(page0.items) == 10
    assert len(page1.items) == 2
    assert page0.total_pages == 2


async def test_get_owned_by_id_raises_for_other_user(session: AsyncSession) -> None:
    owner = await _make_user(session, 910_004)
    other = await _make_user(session, 910_005)
    service = AdvertisementService(AdvertisementRepository(session))
    summary = await service.create_advertisement(
        user_id=owner.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    with pytest.raises(AdvertisementForbiddenError):
        await service.get_owned_by_id(summary.id, other.id)


async def test_get_owned_by_id_raises_when_missing(session: AsyncSession) -> None:
    user = await _make_user(session, 910_006)
    service = AdvertisementService(AdvertisementRepository(session))

    with pytest.raises(AdvertisementNotFoundError):
        await service.get_owned_by_id(uuid.uuid4(), user.id)


async def test_delete_owned_removes_advertisement(session: AsyncSession) -> None:
    user = await _make_user(session, 910_007)
    service = AdvertisementService(AdvertisementRepository(session))
    summary = await service.create_advertisement(
        user_id=user.id, title="Item", description="Desc", price=None, expires_at=None, media_items=[]
    )

    result = await service.delete_owned(summary.id, user.id)
    assert result.channel_message_ids == []

    with pytest.raises(AdvertisementNotFoundError):
        await service.get_owned_by_id(summary.id, user.id)
