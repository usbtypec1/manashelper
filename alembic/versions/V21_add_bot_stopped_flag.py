"""Add a persistent delivery opt-out for stopped or unreachable users.

Revision ID: ba2d4708e921
Revises: 8b8ec5f9757a
"""

from alembic import op
import sqlalchemy as sa

revision = "ba2d4708e921"
down_revision = "8b8ec5f9757a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bot_stopped", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "bot_stopped")
