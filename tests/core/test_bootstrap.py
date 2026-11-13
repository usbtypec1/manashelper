import subprocess
import sys
from textwrap import dedent

EXPECTED_TABLES = {
    "gamification_progress",
    "gamification_achievements",
    "telegram_processed_updates",
    "action_logs",
    "advertisement_ads",
    "advertisement_channel_messages",
    "advertisement_contact_views",
    "advertisement_media",
    "eders_notifications",
    "eders_states",
    "feedback_messages",
    "food_daily_menu_dishes",
    "food_daily_menu_ratings",
    "food_daily_menus",
    "food_dishes",
    "food_menu_notification_settings",
    "notification_settings",
    "obis_sessions",
    "obis_snapshots",
    "obis_user_exam_grades",
    "obis_user_lesson_attendance",
    "timetable_courses",
    "timetable_departments",
    "timetable_faculties",
    "timetable_lesson_history",
    "timetable_lesson_items",
    "timetable_lessons",
    "timetable_rooms",
    "timetable_user_courses",
    "telegram_outbox",
    "telegram_outbox_rate_buckets",
    "users",
}


def test_cold_registry_loads_complete_metadata_and_relationships_without_reexports():
    script = dedent("""\
        from manashelper.core.database import Base
        from manashelper import bootstrap

        assert not Base.metadata.tables
        bootstrap.load_models()
        assert set(Base.metadata.tables) == EXPECTED_TABLES
        assert len(Base.metadata.sorted_tables) == len(EXPECTED_TABLES)

        from manashelper.modules.users.infrastructure.models.user import User
        from manashelper.modules.schedule.infrastructure.models.course import Course
        from manashelper.modules.food_menu.infrastructure.models.daily_menu import DailyMenu
        from manashelper.modules.food_menu.infrastructure.models.dish import Dish

        assert User.tracked_courses.property.mapper.class_ is Course
        assert Course.users.property.mapper.class_ is User
        assert DailyMenu.dishes.property.mapper.class_ is Dish
        assert Base.metadata.tables['timetable_user_courses'].c.user_id.references(User.__table__.c.id)
        assert Base.metadata.tables['food_daily_menu_dishes'].c.dish_id.references(Dish.__table__.c.id)
        model_names = {mapper.class_.__name__ for mapper in Base.registry.mappers}
        assert not model_names.intersection(vars(bootstrap))
    """)
    result = subprocess.run(
        [sys.executable, "-c", f"EXPECTED_TABLES = {EXPECTED_TABLES!r}\n" + script], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_model_registration_is_idempotent_in_a_cold_process():
    script = dedent("""\
        import importlib.util

        from manashelper.core.database import Base
        from manashelper.bootstrap import load_models

        load_models()
        tables = dict(Base.metadata.tables)
        mappers = set(Base.registry.mappers)
        load_models()
        assert dict(Base.metadata.tables) == tables
        assert set(Base.registry.mappers) == mappers
        assert importlib.util.find_spec('manashelper.db') is None
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
