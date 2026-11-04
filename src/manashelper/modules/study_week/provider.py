from dishka import Provider, Scope, provide

from manashelper.modules.study_week.application.use_cases.get_study_week import GetStudyWeekUseCase


class StudyWeekProvider(Provider):
    scope = Scope.REQUEST
    get_study_week = provide(GetStudyWeekUseCase)
