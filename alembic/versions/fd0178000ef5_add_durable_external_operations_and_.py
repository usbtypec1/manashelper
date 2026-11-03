"""add durable external operations and secret handles

Revision ID: fd0178000ef5
Revises: 2cf16577afaf
Create Date: 2026-11-02 23:35:41.500647

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fd0178000ef5"
down_revision: Union[str, Sequence[str], None] = "2cf16577afaf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_ui_dialog_status", "ui_dialog_sessions", type_="check")
    op.create_check_constraint(
        "ck_ui_dialog_status",
        "ui_dialog_sessions",
        "status IN ('running','waiting_button','waiting_input','waiting_effect',"
        "'completed','cancelled','handed_off','failed')",
    )
    op.drop_index("uq_ui_dialog_active_chat", table_name="ui_dialog_sessions")
    op.create_index(
        "uq_ui_dialog_active_chat",
        "ui_dialog_sessions",
        ["chat_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running','waiting_button','waiting_input','waiting_effect')"),
    )
    op.create_table(
        "ui_external_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("flow_id", sa.String(length=32), nullable=False),
        sa.Column("flow_version", sa.Integer(), nullable=False),
        sa.Column("node_id", sa.String(length=32), nullable=False),
        sa.Column("delegate_id", sa.String(length=120), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[a-z][a-z0-9_]{0,63}$'", name="ck_ui_external_error_code"
        ),
        sa.CheckConstraint(
            "status IN ('pending','unknown','succeeded','failed','applied')", name="ck_ui_external_status"
        ),
        sa.CheckConstraint(
            "revision >= 0 AND flow_version >= 1 AND contract_version >= 1", name="ck_ui_external_versions"
        ),
        sa.CheckConstraint("user_id > 0 AND chat_id <> 0", name="ck_ui_external_identity"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["ui_dialog_sessions.id"], name="fk_ui_external_session", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ui_external_operations"),
        sa.UniqueConstraint("session_id", "revision", "node_id", name="uq_ui_external_position"),
    )
    op.create_index("ix_ui_external_pending", "ui_external_operations", ["status", "created_at"], unique=False)
    op.create_table(
        "ui_input_secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("user_id > 0 AND chat_id <> 0", name="ck_ui_input_secret_identity"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["ui_dialog_sessions.id"], name="fk_ui_input_secret_session", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ui_input_secrets"),
    )
    op.create_index("ix_ui_input_secret_expiry", "ui_input_secrets", ["expires_at"], unique=False)
    op.add_column("ui_screen_deliveries", sa.Column("operation_id", sa.Uuid(), nullable=True))
    op.add_column("ui_screen_deliveries", sa.Column("message_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.alter_column("ui_screen_deliveries", "update_id", existing_type=sa.BIGINT(), nullable=True)
    op.create_unique_constraint("uq_ui_screen_operation", "ui_screen_deliveries", ["operation_id"])
    op.create_foreign_key(
        "fk_ui_screen_operation",
        "ui_screen_deliveries",
        "ui_external_operations",
        ["operation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_ui_screen_origin", "ui_screen_deliveries", "(update_id IS NULL) <> (operation_id IS NULL)"
    )
    op.add_column("ui_user_locations", sa.Column("operation_id", sa.Uuid(), nullable=True))
    op.alter_column("ui_user_locations", "update_id", existing_type=sa.BIGINT(), nullable=True)
    op.create_foreign_key(
        "fk_ui_location_operation",
        "ui_user_locations",
        "ui_external_operations",
        ["operation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("ui_user_transitions", sa.Column("operation_id", sa.Uuid(), nullable=True))
    op.alter_column("ui_user_transitions", "update_id", existing_type=sa.BIGINT(), nullable=True)
    op.create_unique_constraint("uq_ui_transition_operation", "ui_user_transitions", ["operation_id"])
    op.create_foreign_key(
        "fk_ui_transition_operation",
        "ui_user_transitions",
        "ui_external_operations",
        ["operation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Hold out writers during preflight and contraction. Retain durable work and history
    # rather than erase them to make an older binary fit.
    op.execute(
        "LOCK TABLE ui_dialog_sessions, ui_external_operations, ui_input_secrets, "
        "ui_screen_deliveries, ui_user_locations, ui_user_transitions IN ACCESS EXCLUSIVE MODE"
    )
    op.execute(
        """DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM ui_dialog_sessions WHERE status = 'waiting_effect')
                OR EXISTS (SELECT 1 FROM ui_external_operations)
                OR EXISTS (SELECT 1 FROM ui_input_secrets)
                OR EXISTS (SELECT 1 FROM ui_screen_deliveries
                           WHERE operation_id IS NOT NULL OR update_id IS NULL)
                OR EXISTS (SELECT 1 FROM ui_user_locations
                           WHERE operation_id IS NOT NULL OR update_id IS NULL)
                OR EXISTS (SELECT 1 FROM ui_user_transitions
                           WHERE operation_id IS NOT NULL OR update_id IS NULL)
            THEN
                RAISE EXCEPTION 'Cannot downgrade durable effects while new state or history exists; '
                                'roll back the application with the expanded schema retained';
            END IF;
        END $$"""
    )
    op.drop_constraint("fk_ui_transition_operation", "ui_user_transitions", type_="foreignkey")
    op.drop_constraint("uq_ui_transition_operation", "ui_user_transitions", type_="unique")
    op.alter_column("ui_user_transitions", "update_id", existing_type=sa.BIGINT(), nullable=False)
    op.drop_column("ui_user_transitions", "operation_id")
    op.drop_constraint("fk_ui_location_operation", "ui_user_locations", type_="foreignkey")
    op.alter_column("ui_user_locations", "update_id", existing_type=sa.BIGINT(), nullable=False)
    op.drop_column("ui_user_locations", "operation_id")
    op.drop_constraint("ck_ui_screen_origin", "ui_screen_deliveries", type_="check")
    op.drop_constraint("fk_ui_screen_operation", "ui_screen_deliveries", type_="foreignkey")
    op.drop_constraint("uq_ui_screen_operation", "ui_screen_deliveries", type_="unique")
    op.alter_column("ui_screen_deliveries", "update_id", existing_type=sa.BIGINT(), nullable=False)
    op.drop_column("ui_screen_deliveries", "message_ids")
    op.drop_column("ui_screen_deliveries", "operation_id")
    op.drop_index("ix_ui_input_secret_expiry", table_name="ui_input_secrets")
    op.drop_table("ui_input_secrets")
    op.drop_index("ix_ui_external_pending", table_name="ui_external_operations")
    op.drop_table("ui_external_operations")
    op.drop_index("uq_ui_dialog_active_chat", table_name="ui_dialog_sessions")
    op.create_index(
        "uq_ui_dialog_active_chat",
        "ui_dialog_sessions",
        ["chat_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('running','waiting_button','waiting_input')"),
    )
    op.drop_constraint("ck_ui_dialog_status", "ui_dialog_sessions", type_="check")
    op.create_check_constraint(
        "ck_ui_dialog_status",
        "ui_dialog_sessions",
        "status IN ('running','waiting_button','waiting_input','completed','cancelled','handed_off','failed')",
    )
