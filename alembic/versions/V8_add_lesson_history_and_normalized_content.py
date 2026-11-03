"""add lesson history and normalized content

Revision ID: b3f7e1a9c4d2
Revises: 9f3e5af84cee
Create Date: 2026-09-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7e1a9c4d2'
down_revision: Union[str, Sequence[str], None] = '9f3e5af84cee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('lessons', sa.Column('normalized_content', sa.Text(), server_default='', nullable=False))
    op.create_table('lesson_history',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('time_range', sa.String(length=16), nullable=False),
    sa.Column('previous_content', sa.Text(), nullable=True),
    sa.Column('new_content', sa.Text(), nullable=True),
    sa.Column('changed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('lesson_history')
    op.drop_column('lessons', 'normalized_content')
