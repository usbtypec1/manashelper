"""add advertising platform

Revision ID: f50277a96f71
Revises: a1b2c3d4e5f6
Create Date: 2026-09-22 14:21:25.386781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f50277a96f71'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), server_default='user', nullable=False),
    )

    op.create_table(
        'user_phone_numbers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'phone_number'),
    )

    op.create_table(
        'advertisements',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=False),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('rejection_comment', sa.String(length=512), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_advertisements_user_id', 'advertisements', ['user_id'])
    op.create_index('ix_advertisements_status', 'advertisements', ['status'])
    op.create_index('ix_advertisements_expires_at', 'advertisements', ['expires_at'])

    op.create_table(
        'advertisement_media',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('advertisement_id', sa.Uuid(), nullable=False),
        sa.Column('file_id', sa.String(length=255), nullable=False),
        sa.Column('media_type', sa.String(length=10), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['advertisement_id'], ['advertisements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('advertisement_id', 'position'),
    )
    op.create_index('ix_advertisement_media_advertisement_id', 'advertisement_media', ['advertisement_id'])

    op.create_table(
        'advertisement_channel_messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('advertisement_id', sa.Uuid(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['advertisement_id'], ['advertisements.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_advertisement_channel_messages_advertisement_id', 'advertisement_channel_messages', ['advertisement_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_advertisement_channel_messages_advertisement_id', table_name='advertisement_channel_messages')
    op.drop_table('advertisement_channel_messages')

    op.drop_index('ix_advertisement_media_advertisement_id', table_name='advertisement_media')
    op.drop_table('advertisement_media')

    op.drop_index('ix_advertisements_expires_at', table_name='advertisements')
    op.drop_index('ix_advertisements_status', table_name='advertisements')
    op.drop_index('ix_advertisements_user_id', table_name='advertisements')
    op.drop_table('advertisements')

    op.drop_table('user_phone_numbers')

    op.drop_column('users', 'role')
