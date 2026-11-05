"""Add opt-in achievement access and academic progress counters."""
from alembic import op
import sqlalchemy as sa

revision = "V29"
down_revision = "V28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gamification_progress", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("gamification_progress", sa.Column("aa_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("gamification_progress", sa.Column("attendance_marker", sa.String(64)))
    op.add_column("gamification_progress", sa.Column("attendance_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("gamification_progress", "attendance_count")
    op.drop_column("gamification_progress", "attendance_marker")
    op.drop_column("gamification_progress", "aa_count")
    op.drop_column("gamification_progress", "enabled")
