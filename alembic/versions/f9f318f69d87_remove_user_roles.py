"""remove user roles

Revision ID: f9f318f69d87
Revises: d26ff98f15ff
Create Date: 2026-09-22 16:00:23.502829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9f318f69d87'
down_revision: Union[str, Sequence[str], None] = 'd26ff98f15ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('users', 'role')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), server_default='user', nullable=False),
    )
