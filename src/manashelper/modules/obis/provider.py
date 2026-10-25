from dishka import Provider, Scope, provide

from manashelper.modules.obis.application.credentials import ObisCredentialsService
from manashelper.modules.obis.application.notification import ObisNotificationService
from manashelper.modules.obis.application.obis import ObisService
from manashelper.modules.obis.application.polling import PollObisUser
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.credentials_repository import ObisCredentialsRepository
from manashelper.modules.obis.infrastructure.crypto import CryptoService
from manashelper.modules.obis.infrastructure.user_exam_grade_repository import UserExamGradeRepository
from manashelper.modules.obis.infrastructure.user_lesson_attendance_repository import UserLessonAttendanceRepository


class ObisProvider(Provider):
    scope = Scope.REQUEST

    client = provide(ObisClient, scope=Scope.APP)
    crypto = provide(CryptoService, scope=Scope.APP)
    credentials_repository = provide(ObisCredentialsRepository)
    credentials = provide(ObisCredentialsService)
    grades = provide(UserExamGradeRepository)
    attendance = provide(UserLessonAttendanceRepository)
    service = provide(ObisService)
    notifications = provide(ObisNotificationService)
    polling = provide(PollObisUser)
