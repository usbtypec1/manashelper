"""Add eders snapshots, reminder settings and delivery state.

Revision ID: b84d3a291f07
Revises: a0dfb70232f1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b84d3a291f07"
down_revision: str | Sequence[str] | None = "a0dfb70232f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eders_states",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("credential_marker", sa.String(64)),
        sa.Column("snapshot", sa.Text()),
        *(
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true())
            for name in ("day_before", "two_hours_before", "openings", "deadline_changes", "hide_archived")
        ),
    )
    op.create_table(
        "eders_notifications",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_key", sa.String(64), primary_key=True),
        sa.Column("activity_key", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("previous_deadline", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_eders_notifications_due_at", "eders_notifications", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_eders_notifications_due_at", table_name="eders_notifications")
    op.drop_table("eders_notifications")
    op.drop_table("eders_states")
