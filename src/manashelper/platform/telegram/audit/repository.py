import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from manashelper.db.models import ActionLog


class ActionLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, chat_id: int, user_id: int, callback_query_data: str | None, message_text: str | None) -> None:
        self._session.add(
            ActionLog(
                id=uuid.uuid4(),
                chat_id=chat_id,
                user_id=user_id,
                callback_query_data=callback_query_data,
                message_text=message_text,
            )
        )
