import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.db.base import Base

if TYPE_CHECKING:
    from manashelper.db.models.dish import Dish

daily_menu_dishes = Table(
    "daily_menu_dishes",
    Base.metadata,
    Column("menu_id", ForeignKey("daily_menus.id"), primary_key=True),
    Column("dish_id", ForeignKey("dishes.id"), primary_key=True),
)


class DailyMenu(Base):
    __tablename__ = "daily_menus"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(unique=True)
    views_count: Mapped[int] = mapped_column(default=0)

    dishes: Mapped[list["Dish"]] = relationship(secondary=daily_menu_dishes)
