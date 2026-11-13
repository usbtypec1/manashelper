"""Explicit ORM registration at application, Alembic and test bootstrap."""

# Imports inside load_models register mapped classes; they are not re-exports.
# ruff: noqa: F401


def load_models() -> None:
    from manashelper.core.database import Base
    from manashelper.modules.advertisements.infrastructure.models.advertisement import Advertisement
    from manashelper.modules.advertisements.infrastructure.models.advertisement_channel_message import (
        AdvertisementChannelMessage,
    )
    from manashelper.modules.advertisements.infrastructure.models.advertisement_contact_view import (
        AdvertisementContactView,
    )
    from manashelper.modules.advertisements.infrastructure.models.advertisement_media import AdvertisementMedia
    from manashelper.modules.eders.infrastructure.models.eders import EdersNotification, EdersState
    from manashelper.modules.feedback.orm import FeedbackMessage
    from manashelper.modules.food_menu.infrastructure.models.daily_menu import DailyMenu, daily_menu_dishes
    from manashelper.modules.food_menu.infrastructure.models.daily_menu_rating import DailyMenuRating
    from manashelper.modules.food_menu.infrastructure.models.dish import Dish
    from manashelper.modules.food_menu.infrastructure.models.food_menu_notification_settings import (
        FoodMenuNotificationSettings,
    )
    from manashelper.modules.gamification.infrastructure.models.achievement import GamificationProgress, UserAchievement
    from manashelper.modules.notifications.orm import NotificationSettings
    from manashelper.modules.obis.infrastructure.models.session import ObisSession
    from manashelper.modules.obis.infrastructure.models.snapshot import ObisSnapshot
    from manashelper.modules.obis.infrastructure.models.user_exam_grade import UserExamGrade
    from manashelper.modules.obis.infrastructure.models.user_lesson_attendance import UserLessonAttendance
    from manashelper.modules.schedule.infrastructure.models.associations import user_courses
    from manashelper.modules.schedule.infrastructure.models.course import Course
    from manashelper.modules.schedule.infrastructure.models.department import Department
    from manashelper.modules.schedule.infrastructure.models.faculty import Faculty
    from manashelper.modules.schedule.infrastructure.models.lesson import Lesson
    from manashelper.modules.schedule.infrastructure.models.lesson_history import LessonHistory
    from manashelper.modules.schedule.infrastructure.models.lesson_item import LessonItem
    from manashelper.modules.schedule.infrastructure.models.room import Room
    from manashelper.modules.users.infrastructure.models.user import User
    from manashelper.platform.telegram.audit.orm import ActionLog
    from manashelper.platform.telegram.outbox.models import OutboxMessage, OutboxRateBucket
    from manashelper.platform.telegram.webhook_models import ProcessedTelegramUpdate

    Base.registry.configure()
