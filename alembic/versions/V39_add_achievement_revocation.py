"""Retain withdrawn awards and identify their pending notifications."""

import sqlalchemy as sa

from alembic import op

revision = "V39"
down_revision = "V38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gamification_achievements", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE telegram_outbox
        SET source_keys = jsonb_build_array(deduplication_key)
        WHERE category = 'achievement'
          AND status = 'pending'
          AND source_keys = '[]'::jsonb
          AND deduplication_key LIKE 'achievement:%'
        """
    )


def downgrade() -> None:
    op.drop_column("gamification_achievements", "revoked_at")
