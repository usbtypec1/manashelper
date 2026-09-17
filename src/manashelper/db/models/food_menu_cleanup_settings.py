from datetime import datetime

from sqlalchemy import BigInteger, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from manashelper.db.base import Base

DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES = 180


class FoodMenuCleanupSettings(Base):
    """Per-*chat* (not per-user) setting for how long a chat's food menu messages stay before being
    auto-deleted. Keyed by `chat_id` rather than a `users.id` foreign key because it also applies to group
    chats, which have no `User` row of their own — see bot/routers/food_menu_cleanup.py."""

    __tablename__ = "food_menu_cleanup_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # NULL means auto-delete is turned off for this chat. No ORM-level `default=` here on purpose:
    # SQLAlchemy's scalar column default fires whenever the value is None — including an explicit
    # "disabled" assignment — which would make it impossible to ever persist NULL. The Python-side
    # default (DEFAULT_FOOD_MENU_CLEANUP_DELAY_MINUTES) is applied explicitly instead, by the
    # repository's `get_or_create`; `server_default` stays for rows inserted outside the ORM.
    delay_minutes: Mapped[int | None] = mapped_column(SmallInteger, server_default="180")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
