"""add student questions responses

Revision ID: 6285694aafa1
Revises: b84d3a291f07
Create Date: 2026-10-01 15:10:51.241188

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6285694aafa1"
down_revision: str | Sequence[str] | None = "b84d3a291f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "student_questions_responses",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("course", sa.String(length=16), nullable=False),
        sa.Column("had_questions", sa.Boolean(), nullable=False),
        sa.Column("questions", sa.Text(), nullable=True),
        sa.Column("found_answers", sa.Boolean(), nullable=True),
        sa.Column("answer_sources", sa.Text(), nullable=True),
        sa.Column("wants_beta", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("student_questions_responses")
