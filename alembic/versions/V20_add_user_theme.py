"""add user theme

Revision ID: 8b8ec5f9757a
Revises: 866ce071a543
Create Date: 2026-10-30 11:14:52.388231

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b8ec5f9757a'
down_revision: Union[str, Sequence[str], None] = '866ce071a543'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('theme', sa.String(length=16), server_default='basic', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'theme')
