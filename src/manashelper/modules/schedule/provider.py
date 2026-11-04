from dishka import Provider, Scope, provide

from manashelper.modules.schedule.application.course import CourseQuery
from manashelper.modules.schedule.application.department import DepartmentQuery
from manashelper.modules.schedule.application.faculty import FacultyQuery
from manashelper.modules.schedule.application.lesson_search import LessonSearchQuery
from manashelper.modules.schedule.application.schedule import ScheduleQuery
from manashelper.modules.schedule.application.use_cases.sync_course_timetable import SyncCourseTimetableUseCase
from manashelper.modules.schedule.application.use_cases.sync_timetable import SyncTimetableUseCase
from manashelper.modules.schedule.application.use_cases.toggle_tracked_course import ToggleTrackedCourseUseCase
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository
from manashelper.modules.schedule.infrastructure.repositories.department import DepartmentRepository
from manashelper.modules.schedule.infrastructure.repositories.faculty import FacultyRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson import LessonRepository
from manashelper.modules.schedule.infrastructure.repositories.lesson_history import LessonHistoryRepository
from manashelper.modules.schedule.infrastructure.timetable_client import TimetableClient


class ScheduleProvider(Provider):
    scope = Scope.REQUEST

    toggle_tracked_course_use_case = provide(ToggleTrackedCourseUseCase)

    client = provide(TimetableClient, scope=Scope.APP)
    faculties = provide(FacultyRepository)
    departments = provide(DepartmentRepository)
    courses = provide(CourseRepository)
    lessons = provide(LessonRepository)
    history = provide(LessonHistoryRepository)
    faculty_query = provide(FacultyQuery)
    department_query = provide(DepartmentQuery)
    course_query = provide(CourseQuery)
    schedule = provide(ScheduleQuery)
    search = provide(LessonSearchQuery)
    sync = provide(SyncTimetableUseCase)
    tracking = provide(CourseTrackingRepository)
    sync_course = provide(SyncCourseTimetableUseCase)
