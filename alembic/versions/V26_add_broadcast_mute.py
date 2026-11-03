"""Add temporary admin broadcast mute.

Revision ID: V26
Revises: f62b3a09cd71
"""

import sqlalchemy as sa

from alembic import op

revision = "V26"
down_revision = "f62b3a09cd71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_settings", sa.Column("broadcast_muted_until", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "broadcast_muted_until")
