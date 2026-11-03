from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from common.database import Base
from ui_flows.domain.schema import Scalar


class UiFlowRollout(Base):
    __tablename__ = "ui_flow_rollout"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ui_rollout_singleton"),
        CheckConstraint("mode IN ('admin','all','off')", name="ck_ui_rollout_mode"),
        CheckConstraint("revision >= 0", name="ck_ui_rollout_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    mode: Mapped[str] = mapped_column(String(8))
    revision: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int | None] = mapped_column(BigInteger)


class UiFlow(Base):
    __tablename__ = "ui_flows"
    __table_args__ = (
        CheckConstraint("draft_revision >= 0", name="ck_ui_flow_draft_revision"),
        ForeignKeyConstraint(
            ["id", "published_version"],
            ["ui_flow_versions.flow_id", "ui_flow_versions.version"],
            name="fk_ui_flow_published_version",
            use_alter=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    draft_revision: Mapped[int] = mapped_column(Integer, default=0)
    published_version: Mapped[int | None] = mapped_column(Integer)


class UiFlowVersion(Base):
    __tablename__ = "ui_flow_versions"
    __table_args__ = (
        UniqueConstraint("flow_id", "draft_revision", name="uq_ui_flow_version_draft"),
        CheckConstraint("version >= 1 AND draft_revision >= 0", name="ck_ui_flow_version_revision"),
    )

    flow_id: Mapped[str] = mapped_column(ForeignKey("ui_flows.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_revision: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    author_id: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    text_catalog_release: Mapped[int | None] = mapped_column(
        ForeignKey("text_catalog_releases.id", name="fk_ui_flow_text_catalog_release"), nullable=True
    )
    dependencies: Mapped[dict[str, int] | None] = mapped_column(JSONB, nullable=True)


class UiDialogSession(Base):
    __tablename__ = "ui_dialog_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["flow_id", "flow_version"],
            ["ui_flow_versions.flow_id", "ui_flow_versions.version"],
            name="fk_ui_dialog_version",
        ),
        CheckConstraint("revision >= 0", name="ck_ui_dialog_revision"),
        CheckConstraint("effect_revision IS NULL OR effect_revision >= 0", name="ck_ui_dialog_effect_revision"),
        CheckConstraint(
            "status IN ('running','waiting_button','waiting_input','waiting_effect',"
            "'completed','cancelled','handed_off','failed')",
            name="ck_ui_dialog_status",
        ),
        Index(
            "uq_ui_dialog_active_chat",
            "chat_id",
            unique=True,
            postgresql_where=text("status IN ('running','waiting_button','waiting_input','waiting_effect')"),
        ),
        Index("ix_ui_dialog_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    flow_id: Mapped[str] = mapped_column(String(32))
    flow_version: Mapped[int] = mapped_column(Integer)
    trigger_release: Mapped[int | None] = mapped_column(
        ForeignKey("ui_trigger_releases.id", name="fk_ui_dialog_trigger_release"), nullable=True
    )
    node_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Scalar]] = mapped_column(JSONB)
    frames: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    effect_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UiFlowEvent(Base):
    __tablename__ = "ui_flow_events"
    __table_args__ = (
        CheckConstraint("update_id >= 0 AND revision >= 0", name="ck_ui_flow_event_identity"),
        Index("ix_ui_flow_event_session", "session_id", "update_id"),
    )

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("ui_dialog_sessions.id", ondelete="CASCADE"))
    result_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ui_dialog_sessions.id", ondelete="SET NULL", name="fk_ui_event_result_session"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    from_step: Mapped[str | None] = mapped_column(String(32))
    to_step: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiScreenDelivery(Base):
    __tablename__ = "ui_screen_deliveries"
    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_ui_screen_operation"),
        CheckConstraint("(update_id IS NULL) <> (operation_id IS NULL)", name="ck_ui_screen_origin"),
        CheckConstraint("revision >= 0", name="ck_ui_screen_revision"),
        CheckConstraint("status IN ('pending','sent','failed','unknown')", name="ck_ui_screen_status"),
        Index("ix_ui_screen_session_created", "session_id", "created_at"),
    )

    token: Mapped[str] = mapped_column(String(16), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("ui_dialog_sessions.id", ondelete="CASCADE"))
    update_id: Mapped[int | None] = mapped_column(
        ForeignKey("ui_flow_events.update_id", ondelete="CASCADE"), unique=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ui_external_operations.id", ondelete="CASCADE", name="fk_ui_screen_operation")
    )
    revision: Mapped[int] = mapped_column(Integer)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    screen: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(8))
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    message_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiUserLocation(Base):
    __tablename__ = "ui_user_locations"
    __table_args__ = (CheckConstraint("owner IN ('runtime','legacy','unknown')", name="ck_ui_location_owner"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    owner: Mapped[str] = mapped_column(String(8))
    session_id: Mapped[UUID | None] = mapped_column(ForeignKey("ui_dialog_sessions.id", ondelete="CASCADE"))
    legacy_state: Mapped[str | None] = mapped_column(String(200))
    handler: Mapped[str | None] = mapped_column(String(200))
    update_id: Mapped[int | None] = mapped_column(BigInteger)
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ui_external_operations.id", ondelete="SET NULL", name="fk_ui_location_operation")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiUserTransition(Base):
    __tablename__ = "ui_user_transitions"
    __table_args__ = (
        Index("ix_ui_transition_user_id", "user_id", "id"),
        UniqueConstraint("operation_id", name="uq_ui_transition_operation"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    update_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ui_external_operations.id", ondelete="SET NULL", name="fk_ui_transition_operation")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    owner: Mapped[str] = mapped_column(String(8))
    flow_id: Mapped[str | None] = mapped_column(String(32))
    flow_version: Mapped[int | None] = mapped_column(Integer)
    from_step: Mapped[str | None] = mapped_column(String(200))
    to_step: Mapped[str | None] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
