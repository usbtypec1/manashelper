"""add pinned scenario dependencies and durable call frames

Revision ID: 2cf16577afaf
Revises: 2deed60a5bfd
Create Date: 2026-11-02 22:55:08.809708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2cf16577afaf'
down_revision: Union[str, Sequence[str], None] = '2deed60a5bfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable columns keep old writers and historical v1 documents compatible.
    op.add_column('ui_dialog_sessions', sa.Column('frames', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('ui_flow_versions', sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Roll back application/pointers first; schema downgrade removes v2 frame history.
    op.drop_column('ui_flow_versions', 'dependencies')
    op.drop_column('ui_dialog_sessions', 'frames')
