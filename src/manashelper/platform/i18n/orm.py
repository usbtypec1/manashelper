"""Draft/pointer state and immutable published user-text snapshots."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from common.database import Base


class TextCatalogRelease(Base):
    __tablename__ = "text_catalog_releases"
    __table_args__ = (
        CheckConstraint("draft_revision >= 0", name="ck_text_catalog_release_revision"),
        UniqueConstraint("draft_revision", name="uq_text_catalog_release_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    draft_revision: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    author_id: Mapped[int | None] = mapped_column(BigInteger)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TextCatalogState(Base):
    __tablename__ = "text_catalog_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_text_catalog_state_singleton"),
        CheckConstraint("revision >= 0", name="ck_text_catalog_state_revision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(Integer)
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    current_release: Mapped[int] = mapped_column(
        ForeignKey("text_catalog_releases.id", name="fk_text_catalog_current_release"), nullable=False
    )
