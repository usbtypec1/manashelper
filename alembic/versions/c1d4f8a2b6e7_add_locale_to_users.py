"""add locale to users

Revision ID: c1d4f8a2b6e7
Revises: b3f7e1a9c4d2
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d4f8a2b6e7'
down_revision: Union[str, Sequence[str], None] = 'b3f7e1a9c4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('locale', sa.String(length=2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'locale')
