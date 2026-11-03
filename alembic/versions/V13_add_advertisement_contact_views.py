"""add advertisement contact views

Revision ID: d26ff98f15ff
Revises: f50277a96f71
Create Date: 2026-09-22 15:39:33.452966

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd26ff98f15ff'
down_revision: Union[str, Sequence[str], None] = 'f50277a96f71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'advertisement_contact_views',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('advertisement_id', sa.Uuid(), nullable=False),
        sa.Column('viewer_user_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['advertisement_id'], ['advertisements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['viewer_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_advertisement_contact_views_advertisement_id', 'advertisement_contact_views', ['advertisement_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_advertisement_contact_views_advertisement_id', table_name='advertisement_contact_views')
    op.drop_table('advertisement_contact_views')
