import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import User
from manashelper.repositories.feedback_repository import FeedbackRepository
from manashelper.services.feedback import FeedbackNotFoundError, FeedbackService


async def _make_user(session: AsyncSession, user_id: int) -> User:
    user = User(id=user_id, full_name="Test User", username=None)
    session.add(user)
    await session.flush()
    return user


async def test_submit_creates_feedback(session: AsyncSession) -> None:
    user = await _make_user(session, 940_001)
    service = FeedbackService(FeedbackRepository(session))

    summary = await service.submit(user.id, "Hello, I have a question")

    assert summary.user_id == user.id
    assert summary.body == "Hello, I have a question"


async def test_record_admin_chat_message_allows_lookup(session: AsyncSession) -> None:
    user = await _make_user(session, 940_002)
    service = FeedbackService(FeedbackRepository(session))
    summary = await service.submit(user.id, "Hello")

    await service.record_admin_chat_message(summary.id, 12345)
    found = await service.get_by_admin_chat_message_id(12345)

    assert found is not None
    assert found.id == summary.id
    assert found.user_id == user.id


async def test_get_by_admin_chat_message_id_returns_none_when_unmatched(session: AsyncSession) -> None:
    service = FeedbackService(FeedbackRepository(session))

    assert await service.get_by_admin_chat_message_id(999_999) is None


async def test_record_admin_chat_message_raises_when_missing(session: AsyncSession) -> None:
    service = FeedbackService(FeedbackRepository(session))

    with pytest.raises(FeedbackNotFoundError):
        await service.record_admin_chat_message(uuid.uuid4(), 1)
