from dishka import Provider, Scope, provide

from manashelper.modules.feedback.application.use_cases.record_feedback_admin_message import (
    RecordFeedbackAdminMessageUseCase,
)
from manashelper.modules.feedback.application.use_cases.submit_feedback import SubmitFeedbackUseCase
from manashelper.modules.feedback.repository import FeedbackRepository
from manashelper.modules.feedback.service import FeedbackQuery


class FeedbackProvider(Provider):
    scope = Scope.REQUEST

    record_feedback_admin_message_use_case = provide(RecordFeedbackAdminMessageUseCase)

    submit_feedback_use_case = provide(SubmitFeedbackUseCase)

    repository = provide(FeedbackRepository)
    feedback_query = provide(FeedbackQuery)
