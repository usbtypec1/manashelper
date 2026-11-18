import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from manashelper.core.database import Base


class DishRating(Base):
    __tablename__ = "food_dish_ratings"
    __table_args__ = (CheckConstraint("score BETWEEN 1 AND 5", name="ck_food_dish_ratings_score"),)

    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("food_dishes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    score: Mapped[int]
