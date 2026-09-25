import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import FeedbackMessage


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, feedback: FeedbackMessage) -> None:
        self._session.add(feedback)

    async def get_by_id(self, feedback_id: uuid.UUID) -> FeedbackMessage | None:
        return await self._session.get(FeedbackMessage, feedback_id)

    async def get_by_admin_chat_message_id(self, message_id: int) -> FeedbackMessage | None:
        result = await self._session.execute(
            select(FeedbackMessage).where(FeedbackMessage.admin_chat_message_id == message_id)
        )
        return result.scalar_one_or_none()
