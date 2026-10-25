from dishka import Provider, Scope, provide

from manashelper.repositories.eders_repository import EdersRepository
from manashelper.repositories.user_exam_grade_repository import UserExamGradeRepository
from manashelper.repositories.user_lesson_attendance_repository import UserLessonAttendanceRepository
from manashelper.scraping.eders_client import EdersClient
from manashelper.scraping.obis_client import ObisClient
from manashelper.services.crypto import CryptoService
from manashelper.services.eders import EdersService
from manashelper.services.eders_tracking import EdersTrackingService
from manashelper.services.obis import ObisService
from manashelper.services.obis_notification import ObisNotificationService
from manashelper.services.study_week import StudyWeekService


class AppProvider(Provider):
    scope = Scope.APP

    crypto_service = provide(CryptoService)
    obis_client = provide(ObisClient)
    eders_client = provide(EdersClient)


class RequestProvider(Provider):
    scope = Scope.REQUEST

    eders_repository = provide(EdersRepository)
    user_exam_grade_repository = provide(UserExamGradeRepository)
    user_lesson_attendance_repository = provide(UserLessonAttendanceRepository)

    obis_service = provide(ObisService)
    eders_service = provide(EdersService)
    eders_tracking_service = provide(EdersTrackingService)
    obis_notification_service = provide(ObisNotificationService)
    study_week_service = provide(StudyWeekService)
