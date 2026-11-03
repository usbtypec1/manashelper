from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.database import Base


class UiTriggerRelease(Base):
    __tablename__ = "ui_trigger_releases"
    __table_args__ = (UniqueConstraint("draft_revision", name="uq_ui_trigger_revision"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    draft_revision: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    author_id: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UiTriggerState(Base):
    __tablename__ = "ui_trigger_state"
    __table_args__ = (CheckConstraint("id = 1 AND revision >= 0", name="ck_ui_trigger_singleton"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(Integer)
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    current_release: Mapped[int | None] = mapped_column(
        ForeignKey("ui_trigger_releases.id", name="fk_ui_trigger_current")
    )


class UiIngressReceipt(Base):
    __tablename__ = "ui_ingress_receipts"
    __table_args__ = (CheckConstraint("bot_id > 0 AND update_id >= 0 AND actor_id > 0", name="ck_ui_ingress_identity"),)
    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    release_id: Mapped[int] = mapped_column(ForeignKey("ui_trigger_releases.id"))
    decision: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
