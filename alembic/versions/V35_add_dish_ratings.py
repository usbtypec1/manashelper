"""Store one rating per user and dish."""

import sqlalchemy as sa

from alembic import op

revision = "V35"
down_revision = "V34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_dish_ratings",
        sa.Column("dish_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dish_id"], ["food_dishes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dish_id", "user_id"),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_food_dish_ratings_score"),
    )
    op.create_index("ix_food_dish_ratings_user_id", "food_dish_ratings", ["user_id"])


def downgrade() -> None:
    op.drop_table("food_dish_ratings")
