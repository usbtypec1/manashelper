"""Preserve existing advertisement contacts and retire profile phone numbers.

Revision ID: f62b3a09cd71
Revises: e5170c4b92a8
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f62b3a09cd71"
down_revision = "e5170c4b92a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "advertisement_ads",
        sa.Column("phone_numbers", postgresql.JSONB(), server_default="[]", nullable=False),
    )
    op.execute("""
        UPDATE advertisement_ads AS advertisement
        SET phone_numbers = phones.numbers
        FROM (
            SELECT user_id, jsonb_agg(phone_number ORDER BY created_at, id) AS numbers
            FROM user_phone_numbers
            GROUP BY user_id
        ) AS phones
        WHERE advertisement.user_id = phones.user_id
    """)
    op.drop_table("user_phone_numbers")


def downgrade() -> None:
    op.create_table(
        "user_phone_numbers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "phone_number"),
    )
    # Restore distinct contacts still present on ads. Phones without ads and old
    # profile row IDs/timestamps cannot be recovered after the profile table drop.
    op.execute("""
        INSERT INTO user_phone_numbers (id, user_id, phone_number)
        SELECT gen_random_uuid(), user_id, phone_number
        FROM (
            SELECT DISTINCT advertisement.user_id, phone.phone_number
            FROM advertisement_ads AS advertisement
            CROSS JOIN LATERAL jsonb_array_elements_text(advertisement.phone_numbers) AS phone(phone_number)
        ) AS contacts
    """)
    op.drop_column("advertisement_ads", "phone_numbers")
