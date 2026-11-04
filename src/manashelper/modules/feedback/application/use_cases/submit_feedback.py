import uuid
from dataclasses import dataclass

from manashelper.modules.feedback.orm import FeedbackMessage
from manashelper.modules.feedback.repository import FeedbackRepository
from manashelper.modules.feedback.service import FeedbackSummary, to_summary


@dataclass(frozen=True, slots=True)
class SubmitFeedbackUseCase:
    feedback_repository: FeedbackRepository

    async def execute(self, user_id: int, body: str) -> FeedbackSummary:
        feedback = FeedbackMessage(id=uuid.uuid4(), user_id=user_id, body=body)
        self.feedback_repository.add(feedback)
        return to_summary(feedback)
