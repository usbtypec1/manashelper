"""Keep administrative blocking separate from bot delivery status."""

import sqlalchemy as sa

from alembic import op

revision = "V37"
down_revision = "V36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_blocked")
