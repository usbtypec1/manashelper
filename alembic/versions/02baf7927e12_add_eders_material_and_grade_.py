"""add eders material and grade notifications

Revision ID: 02baf7927e12
Revises: 6285694aafa1
Create Date: 2026-10-01 16:06:18.351879

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02baf7927e12"
down_revision: str | Sequence[str] | None = "6285694aafa1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("eders_states", sa.Column("new_materials", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("eders_states", sa.Column("grade_changes", sa.Boolean(), server_default="true", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("eders_states", "grade_changes")
    op.drop_column("eders_states", "new_materials")
