"""localize food dishes

Revision ID: V30
Revises: V29
Create Date: 2026-11-08 11:40:42.004764+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'V30'
down_revision: Union[str, Sequence[str], None] = 'V29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("food_dishes", "name", new_column_name="name_tr")
    for locale in ("en", "ru", "ky", "zh"):
        op.add_column("food_dishes", sa.Column(f"name_{locale}", sa.String(255), nullable=True))
    op.add_column("food_dishes", sa.Column("upscaled_photo_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("food_dishes", "upscaled_photo_url")
    for locale in ("zh", "ky", "ru", "en"):
        op.drop_column("food_dishes", f"name_{locale}")
    op.alter_column("food_dishes", "name_tr", new_column_name="name")
