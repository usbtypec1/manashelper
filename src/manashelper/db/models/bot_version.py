import uuid
from datetime import date, datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base


class BotVersion(Base):
    """A single entry in the `/versions` changelog shown to users — see bot/routers/versions.py.

    `sort_order` (not `version`) drives display order, since semver strings don't sort correctly as
    plain text (e.g. "2.10.0" < "2.9.0" lexicographically) — it's a plain ascending release sequence
    number, assigned by semantic version order when the table is seeded/updated."""

    __tablename__ = "bot_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(unique=True)
    sort_order: Mapped[int] = mapped_column(unique=True)
    released_at: Mapped[date]
    # A short, user-facing summary of what changed — not a raw commit/PR log.
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
