"""add feedback messages

Revision ID: a0dfb70232f1
Revises: f9f318f69d87
Create Date: 2026-09-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0dfb70232f1'
down_revision: Union[str, Sequence[str], None] = 'f9f318f69d87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'feedback_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('body', sa.String(length=2000), nullable=False),
        sa.Column('admin_chat_message_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_feedback_messages_admin_chat_message_id', 'feedback_messages', ['admin_chat_message_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_feedback_messages_admin_chat_message_id', table_name='feedback_messages')
    op.drop_table('feedback_messages')
