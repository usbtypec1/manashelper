from dishka import Provider, Scope, provide

from manashelper.services.study_week import StudyWeekService


class RequestProvider(Provider):
    scope = Scope.REQUEST
    study_week_service = provide(StudyWeekService)
