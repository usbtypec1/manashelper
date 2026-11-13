"""Add menu rating and failed course progress for achievements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "V31"
down_revision = "V30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gamification_progress", sa.Column("menu_ratings", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "gamification_progress",
        sa.Column("failed_courses", postgresql.ARRAY(sa.String(32)), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("gamification_progress", "failed_courses")
    op.drop_column("gamification_progress", "menu_ratings")
