from dishka import Provider, Scope, provide

from manashelper.modules.feedback.repository import FeedbackRepository
from manashelper.modules.feedback.service import FeedbackService


class FeedbackProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(FeedbackRepository)
    service = provide(FeedbackService)
