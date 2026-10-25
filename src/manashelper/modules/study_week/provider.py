from dishka import Provider, Scope, provide

from manashelper.modules.study_week.application import GetStudyWeek


class StudyWeekProvider(Provider):
    scope = Scope.REQUEST
    get_study_week = provide(GetStudyWeek)
