"""Add opt-out for material notifications.

Revision ID: c94d3a291f08
Revises: 6285694aafa1
"""

import sqlalchemy as sa

from alembic import op

revision = "c94d3a291f08"
down_revision = "6285694aafa1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eders_states", sa.Column("new_materials", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("eders_states", "new_materials")
