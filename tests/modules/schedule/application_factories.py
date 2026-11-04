from types import SimpleNamespace

from manashelper.modules.schedule.application.course import CourseQuery
from manashelper.modules.schedule.application.use_cases.toggle_tracked_course import ToggleTrackedCourseUseCase


def build_course_service(course_repository, tracking_repository):
    query = CourseQuery(course_repository, tracking_repository)
    return SimpleNamespace(
        get_courses_by_department=query.get_courses_by_department,
        get_all_ids=query.get_all_ids,
        toggle_tracked_course=ToggleTrackedCourseUseCase(
            course_repository=course_repository, tracking_repository=tracking_repository
        ).execute,
    )
