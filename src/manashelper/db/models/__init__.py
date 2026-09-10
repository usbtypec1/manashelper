from manashelper.db.models.associations import user_courses
from manashelper.db.models.course import Course
from manashelper.db.models.daily_menu import DailyMenu, daily_menu_dishes
from manashelper.db.models.daily_menu_rating import DailyMenuRating
from manashelper.db.models.department import Department
from manashelper.db.models.dish import Dish
from manashelper.db.models.faculty import Faculty
from manashelper.db.models.lesson import Lesson
from manashelper.db.models.notification_settings import NotificationSettings
from manashelper.db.models.user import User
from manashelper.db.models.user_exam_grade import UserExamGrade
from manashelper.db.models.user_lesson_attendance import UserLessonAttendance

__all__ = [
    "Course",
    "DailyMenu",
    "DailyMenuRating",
    "Department",
    "Dish",
    "Faculty",
    "Lesson",
    "NotificationSettings",
    "User",
    "UserExamGrade",
    "UserLessonAttendance",
    "daily_menu_dishes",
    "user_courses",
]
