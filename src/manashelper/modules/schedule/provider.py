from dishka import Provider, Scope, provide

from manashelper.modules.schedule.application.course import CourseService
from manashelper.modules.schedule.application.department import DepartmentService
from manashelper.modules.schedule.application.faculty import FacultyService
from manashelper.modules.schedule.application.lesson_search import LessonSearchService
from manashelper.modules.schedule.application.schedule import ScheduleService
from manashelper.modules.schedule.application.sync_course import SyncCourseTimetable
from manashelper.modules.schedule.application.timetable_sync import TimetableSyncService
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository
from manashelper.modules.schedule.infrastructure.repositories.department import DepartmentRepository
from manashelper.modules.schedule.infrastructure.repositories.faculty import FacultyRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_history import LessonHistoryRepository
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
