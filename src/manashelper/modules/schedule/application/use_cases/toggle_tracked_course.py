from dataclasses import dataclass

from manashelper.modules.schedule.application.course import (
    CourseNotFoundError,
    CourseSummary,
    UserNotFoundError,
    to_summaries,
)
from manashelper.modules.schedule.infrastructure.repositories.course import CourseRepository
from manashelper.modules.schedule.infrastructure.repositories.course_tracking import CourseTrackingRepository


@dataclass(frozen=True, slots=True)
class ToggleTrackedCourseUseCase:
    course_repository: CourseRepository
    tracking_repository: CourseTrackingRepository

    async def execute(self, course_id: int, user_id: int) -> list[CourseSummary]:
        course = await self.course_repository.get_by_id(course_id)
        if course is None:
            raise CourseNotFoundError(course_id)
        user = await self.tracking_repository.get_with_tracked_courses(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        tracked_course_ids = {tracked_course.id for tracked_course in user.tracked_courses}
        if course_id in tracked_course_ids:
            user.tracked_courses = [
                tracked_course for tracked_course in user.tracked_courses if tracked_course.id != course_id
            ]
        else:
            user.tracked_courses.append(course)
        sibling_courses = await self.course_repository.get_all_by_department_id(course.department_id)
        updated_tracked_ids = {tracked_course.id for tracked_course in user.tracked_courses}
        return to_summaries(sibling_courses, updated_tracked_ids)
