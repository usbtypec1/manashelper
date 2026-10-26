from dishka import Provider, Scope, provide

from manashelper.modules.student_questions.repository import StudentQuestionsRepository
from manashelper.modules.student_questions.service import StudentQuestionsService


class StudentQuestionsProvider(Provider):
    scope = Scope.REQUEST

    repository = provide(StudentQuestionsRepository)
    service = provide(StudentQuestionsService)
