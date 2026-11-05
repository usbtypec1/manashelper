"""Add achievement progress, awards and completed webhook receipts."""
from alembic import op
import sqlalchemy as sa

revision = "V28"
down_revision = "V27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gamification_progress",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("food_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_food_view", sa.DateTime(timezone=True)),
        sa.Column("night_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_night_date", sa.Date()),
        sa.Column("academic_marker", sa.String(64)),
        sa.Column("academic_term", sa.String(32)),
        sa.Column("gpa_baseline", sa.Numeric(6, 4)),
        sa.Column("gpa_current", sa.Numeric(6, 4)),
    )
    op.create_table(
        "gamification_achievements",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("achievement_key", sa.String(32), primary_key=True),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granted_by", sa.BigInteger()),
    )
    op.create_table(
        "telegram_processed_updates",
        sa.Column("update_id", sa.BigInteger(), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telegram_processed_updates_processed_at", "telegram_processed_updates", ["processed_at"])


def downgrade() -> None:
    op.drop_table("telegram_processed_updates")
    op.drop_table("gamification_achievements")
    op.drop_table("gamification_progress")
