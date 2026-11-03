"""Remove scheduled message deletion and its food menu preferences.

Revision ID: e5170c4b92a8
Revises: df29b7418a60
"""

import sqlalchemy as sa

from alembic import op

revision = "e5170c4b92a8"
down_revision = "df29b7418a60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("scheduled_message_deletions")
    op.drop_table("food_menu_cleanup_settings")


def downgrade() -> None:
    # Restore empty tables only; removed tasks and preferences are not recoverable.
    op.create_table(
        "food_menu_cleanup_settings",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("delay_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("chat_id"),
    )
    op.create_table(
        "scheduled_message_deletions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("delete_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_message_deletions_delete_at", "scheduled_message_deletions", ["delete_at"])
