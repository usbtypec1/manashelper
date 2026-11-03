"""Prefix feature tables without changing their structure or data.

Revision ID: ce84a19d7032
Revises: ba2d4708e921
"""

from alembic import op

revision = "ce84a19d7032"
down_revision = "ba2d4708e921"
branch_labels = None
depends_on = None

TABLE_RENAMES = (
    ("advertisements", "advertisement_ads"),
    ("user_exam_grades", "obis_user_exam_grades"),
    ("user_lesson_attendance", "obis_user_lesson_attendance"),
    ("daily_menus", "food_daily_menus"),
    ("dishes", "food_dishes"),
    ("daily_menu_dishes", "food_daily_menu_dishes"),
    ("daily_menu_ratings", "food_daily_menu_ratings"),
    ("faculties", "timetable_faculties"),
    ("departments", "timetable_departments"),
    ("courses", "timetable_courses"),
    ("lessons", "timetable_lessons"),
    ("lesson_history", "timetable_lesson_history"),
    ("user_courses", "timetable_user_courses"),
)


def upgrade() -> None:
    for previous, current in TABLE_RENAMES:
        op.rename_table(previous, current)


def downgrade() -> None:
    for previous, current in reversed(TABLE_RENAMES):
        op.rename_table(current, previous)
