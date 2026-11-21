"""Store administrative achievement display overrides."""

import sqlalchemy as sa

from alembic import op

revision = "V38"
down_revision = "V37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gamification_achievement_display",
        sa.Column("achievement_key", sa.String(32), primary_key=True),
        sa.Column("custom_name", sa.String(80), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table("gamification_achievement_display")
