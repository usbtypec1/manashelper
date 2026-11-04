from types import SimpleNamespace

from manashelper.modules.feedback.application.use_cases.record_feedback_admin_message import (
    RecordFeedbackAdminMessageUseCase,
)
from manashelper.modules.feedback.application.use_cases.submit_feedback import SubmitFeedbackUseCase
from manashelper.modules.feedback.service import FeedbackQuery


def build_feedback_service(feedback_repository):
    query = FeedbackQuery(feedback_repository)
    return SimpleNamespace(
        get_by_admin_chat_message_id=query.get_by_admin_chat_message_id,
        submit=SubmitFeedbackUseCase(feedback_repository=feedback_repository).execute,
        record_admin_chat_message=RecordFeedbackAdminMessageUseCase(feedback_repository=feedback_repository).execute,
    )
