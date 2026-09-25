import uuid
from dataclasses import dataclass

from manashelper.db.models import FeedbackMessage
from manashelper.repositories.feedback_repository import FeedbackRepository

BODY_MAX_LENGTH = 2000


class FeedbackNotFoundError(Exception):
    def __init__(self, feedback_id: uuid.UUID) -> None:
        super().__init__(f"Feedback message {feedback_id} not found")
        self.feedback_id = feedback_id


@dataclass(frozen=True, slots=True)
class FeedbackSummary:
    id: uuid.UUID
    user_id: int
    body: str


def _to_summary(feedback: FeedbackMessage) -> FeedbackSummary:
    return FeedbackSummary(id=feedback.id, user_id=feedback.user_id, body=feedback.body)


class FeedbackService:
    def __init__(self, feedback_repository: FeedbackRepository) -> None:
        self._feedback_repository = feedback_repository

    async def submit(self, user_id: int, body: str) -> FeedbackSummary:
        feedback = FeedbackMessage(id=uuid.uuid4(), user_id=user_id, body=body)
        self._feedback_repository.add(feedback)
        return _to_summary(feedback)

    async def record_admin_chat_message(self, feedback_id: uuid.UUID, message_id: int) -> None:
        feedback = await self._feedback_repository.get_by_id(feedback_id)
        if feedback is None:
            raise FeedbackNotFoundError(feedback_id)
        feedback.admin_chat_message_id = message_id

    async def get_by_admin_chat_message_id(self, message_id: int) -> FeedbackSummary | None:
        feedback = await self._feedback_repository.get_by_admin_chat_message_id(message_id)
        if feedback is None:
            return None
        return _to_summary(feedback)
