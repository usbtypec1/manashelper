import subprocess
import sys
from textwrap import dedent

EXPECTED_TABLES = {
    "action_logs",
    "advertisement_channel_messages",
    "advertisement_contact_views",
    "advertisement_media",
    "advertisements",
    "courses",
    "daily_menu_dishes",
    "daily_menu_ratings",
    "daily_menus",
    "departments",
    "dishes",
    "eders_notifications",
    "eders_states",
    "faculties",
    "feedback_messages",
    "food_menu_cleanup_settings",
    "food_menu_notification_settings",
    "lesson_history",
    "lessons",
    "notification_settings",
    "scheduled_message_deletions",
    "student_questions_responses",
    "user_courses",
    "user_exam_grades",
    "user_lesson_attendance",
    "user_phone_numbers",
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

        from manashelper.modules.users.infrastructure.user import User
        from manashelper.modules.schedule.infrastructure.models.course import Course
        from manashelper.modules.food_menu.infrastructure.models.daily_menu import DailyMenu
        from manashelper.modules.food_menu.infrastructure.models.dish import Dish

        assert User.tracked_courses.property.mapper.class_ is Course
        assert Course.users.property.mapper.class_ is User
        assert DailyMenu.dishes.property.mapper.class_ is Dish
        assert Base.metadata.tables['user_courses'].c.user_id.references(User.__table__.c.id)
        assert Base.metadata.tables['daily_menu_dishes'].c.dish_id.references(Dish.__table__.c.id)
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
