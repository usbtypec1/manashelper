import uuid
from dataclasses import dataclass

from manashelper.modules.feedback.orm import FeedbackMessage
from manashelper.modules.feedback.repository import FeedbackRepository

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


def to_summary(feedback: FeedbackMessage) -> FeedbackSummary:
    return FeedbackSummary(id=feedback.id, user_id=feedback.user_id, body=feedback.body)


@dataclass(frozen=True, slots=True)
class FeedbackQuery:
    feedback_repository: FeedbackRepository

    async def get_by_admin_chat_message_id(self, message_id: int) -> FeedbackSummary | None:
        feedback = await self.feedback_repository.get_by_admin_chat_message_id(message_id)
        if feedback is None:
            return None
        return to_summary(feedback)
