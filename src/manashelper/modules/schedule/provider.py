from dishka import Provider, Scope, provide

from manashelper.modules.schedule.application.course import CourseService
from manashelper.modules.schedule.application.department import DepartmentService
from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.application.lesson_search import LessonSearchService
from manashelper.modules.schedule.application.schedule import ScheduleService
from manashelper.modules.schedule.application.sync_course import SyncCourseTimetable
from manashelper.modules.schedule.application.timetable_sync import TimetableSyncService
from manashelper.modules.schedule.infrastructure.repositories.course_repository import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking_repository import CourseTrackingRepository
from manashelper.modules.schedule.infrastructure.repositories.department_repository import DepartmentRepository
from manashelper.modules.schedule.infrastructure.repositories.faculty_repository import FacultyRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_history_repository import LessonHistoryRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_repository import LessonRepository
from manashelper.modules.schedule.infrastructure.timetable_client import TimetableClient


class ScheduleProvider(Provider):
    scope = Scope.REQUEST

    client = provide(TimetableClient, scope=Scope.APP)
    faculties = provide(FacultyRepository)
    departments = provide(DepartmentRepository)
    courses = provide(CourseRepository)
    lessons = provide(LessonRepository)
    history = provide(LessonHistoryRepository)
    faculty_service = provide(FacultyService)
    department_service = provide(DepartmentService)
    course_service = provide(CourseService)
    schedule = provide(ScheduleService)
    search = provide(LessonSearchService)
    sync = provide(TimetableSyncService)
    tracking = provide(CourseTrackingRepository)
    sync_course = provide(SyncCourseTimetable)
