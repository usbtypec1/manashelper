"""Persist OBIS retry and manual-login state without changing saved sessions."""

import sqlalchemy as sa

from alembic import op

revision = "V34"
down_revision = "V33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "obis_auth_states",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("manual_required", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("obis_auth_states")
