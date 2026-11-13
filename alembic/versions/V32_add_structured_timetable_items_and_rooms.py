"""Add structured timetable lesson items, room catalog and course level.

Existing slots receive items on their next synchronization; the hourly timetable job also runs at startup.
"""

import sqlalchemy as sa

from alembic import op

revision = "V32"
down_revision = "V31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "timetable_courses",
        sa.Column("level", sa.String(length=16), nullable=False, server_default="bachelor"),
    )
    op.create_table(
        "timetable_lesson_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("teacher", sa.Text(), nullable=False),
        sa.Column("room", sa.Text(), nullable=False),
        sa.Column("teacher_key", sa.Text(), nullable=False),
        sa.Column("room_key", sa.String(length=128), nullable=False),
        sa.Column("subject_key", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["lesson_id"], ["timetable_lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timetable_lesson_items_lesson_id", "timetable_lesson_items", ["lesson_id"])
    op.create_index("ix_timetable_lesson_items_teacher_key", "timetable_lesson_items", ["teacher_key"])
    op.create_index("ix_timetable_lesson_items_room_key", "timetable_lesson_items", ["room_key"])
    op.create_index("ix_timetable_lesson_items_subject_key", "timetable_lesson_items", ["subject_key"])
    op.create_table(
        "timetable_rooms",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("room_key", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timetable_rooms_room_key", "timetable_rooms", ["room_key"])


def downgrade() -> None:
    op.drop_index("ix_timetable_rooms_room_key", table_name="timetable_rooms")
    op.drop_table("timetable_rooms")
    op.drop_index("ix_timetable_lesson_items_subject_key", table_name="timetable_lesson_items")
    op.drop_index("ix_timetable_lesson_items_room_key", table_name="timetable_lesson_items")
    op.drop_index("ix_timetable_lesson_items_teacher_key", table_name="timetable_lesson_items")
    op.drop_index("ix_timetable_lesson_items_lesson_id", table_name="timetable_lesson_items")
    op.drop_table("timetable_lesson_items")
    op.drop_column("timetable_courses", "level")
