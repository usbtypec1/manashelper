"""Remove the retired student survey response table.

Revision ID: df29b7418a60
Revises: ce84a19d7032
"""

import sqlalchemy as sa

from alembic import op

revision = "df29b7418a60"
down_revision = "ce84a19d7032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("student_questions_responses")


def downgrade() -> None:
    # Restore the historical schema only; deleted responses cannot be recovered.
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
