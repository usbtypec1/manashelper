from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from common.database import Base
from ui_flows.domain.schema import DataValue


class UiExternalOperation(Base):
    __tablename__ = "ui_external_operations"
    __table_args__ = (
        UniqueConstraint("session_id", "revision", "node_id", name="uq_ui_external_position"),
        CheckConstraint("user_id > 0 AND chat_id <> 0", name="ck_ui_external_identity"),
        CheckConstraint(
            "revision >= 0 AND flow_version >= 1 AND contract_version >= 1", name="ck_ui_external_versions"
        ),
        CheckConstraint("status IN ('pending','unknown','succeeded','failed','applied')", name="ck_ui_external_status"),
        CheckConstraint(
            "error_code IS NULL OR error_code ~ '^[a-z][a-z0-9_]{0,63}$'", name="ck_ui_external_error_code"
        ),
        Index("ix_ui_external_pending", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("ui_dialog_sessions.id", ondelete="CASCADE", name="fk_ui_external_session")
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(Integer)
    flow_id: Mapped[str] = mapped_column(String(32))
    flow_version: Mapped[int] = mapped_column(Integer)
    node_id: Mapped[str] = mapped_column(String(32))
    delegate_id: Mapped[str] = mapped_column(String(120))
    contract_version: Mapped[int] = mapped_column(Integer)
    arguments: Mapped[dict[str, DataValue]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiInputSecret(Base):
    __tablename__ = "ui_input_secrets"
    __table_args__ = (
        CheckConstraint("user_id > 0 AND chat_id <> 0", name="ck_ui_input_secret_identity"),
        Index("ix_ui_input_secret_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("ui_dialog_sessions.id", ondelete="CASCADE", name="fk_ui_input_secret_session")
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    ciphertext: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
