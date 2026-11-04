import uuid
from dataclasses import dataclass

from manashelper.modules.feedback.repository import FeedbackRepository
from manashelper.modules.feedback.service import FeedbackNotFoundError


@dataclass(frozen=True, slots=True)
class RecordFeedbackAdminMessageUseCase:
    feedback_repository: FeedbackRepository

    async def execute(self, feedback_id: uuid.UUID, message_id: int) -> None:
        feedback = await self.feedback_repository.get_by_id(feedback_id)
        if feedback is None:
            raise FeedbackNotFoundError(feedback_id)
        feedback.admin_chat_message_id = message_id
