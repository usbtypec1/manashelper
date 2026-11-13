"""Add saved OBIS login sessions.

OBIS login now requires a captcha, so polling reuses an encrypted session that the student opens once.
Existing credentials have no session until the student logs in again.
"""

import sqlalchemy as sa
from alembic import op

revision = "V33"
down_revision = "V32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "obis_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("encrypted_cookies", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("obis_sessions")
