import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manashelper.core.database import Base

if TYPE_CHECKING:
    from manashelper.modules.food_menu.infrastructure.models.dish import Dish

daily_menu_dishes = Table(
    "food_daily_menu_dishes",
    Base.metadata,
    Column("menu_id", ForeignKey("food_daily_menus.id"), primary_key=True),
    Column("dish_id", ForeignKey("food_dishes.id"), primary_key=True),
)


class DailyMenu(Base):
    __tablename__ = "food_daily_menus"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(unique=True)
    views_count: Mapped[int] = mapped_column(default=0)

    dishes: Mapped[list["Dish"]] = relationship(secondary=daily_menu_dishes)
