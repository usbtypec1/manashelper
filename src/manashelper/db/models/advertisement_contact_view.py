import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from manashelper.db.base import Base

if TYPE_CHECKING:
    from manashelper.db.models.advertisement import Advertisement


class AdvertisementContactView(Base):
    """Records a viewer opening an ad's contact-reveal deep link (`/start ad_<id>`), so we can tell
    how many people were actually interested in an ad. Never deduplicated - each open is its own row."""

    __tablename__ = "advertisement_contact_views"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    advertisement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertisements.id", ondelete="CASCADE"), index=True)
    viewer_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advertisement: Mapped["Advertisement"] = relationship()
