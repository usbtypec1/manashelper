"""Persist admin broadcast campaigns and their outbox delivery batches."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "V36"
down_revision = "V35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broadcast_campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audience", sa.String(16), nullable=False),
        sa.Column("user_ids", postgresql.JSONB(), nullable=False),
        sa.Column("variants", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_broadcast_campaigns_created_at_id", "broadcast_campaigns", ["created_at", "id"])
    op.add_column("telegram_outbox", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.create_index(
        "ix_telegram_outbox_batch_id_user_id",
        "telegram_outbox",
        ["batch_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_outbox_batch_id_user_id", table_name="telegram_outbox")
    op.drop_column("telegram_outbox", "batch_id")
    op.drop_table("broadcast_campaigns")
