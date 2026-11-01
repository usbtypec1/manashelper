"""track_returned_dialog_sessions

Revision ID: 41edcfaadf86
Revises: 8e3edc9cfd80
Create Date: 2026-11-01 17:11:32.299007

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "41edcfaadf86"
down_revision: str | Sequence[str] | None = "8e3edc9cfd80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("ui_flow_events", sa.Column("result_session_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_ui_event_result_session",
        "ui_flow_events",
        "ui_dialog_sessions",
        ["result_session_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_ui_event_result_session", "ui_flow_events", type_="foreignkey")
    op.drop_column("ui_flow_events", "result_session_id")
