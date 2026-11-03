"""Add immutable text releases and pin existing flow versions to the PO baseline.

Revision ID: d91e6b1a7f23
Revises: 17f4cf2162e2
Create Date: 2026-11-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d91e6b1a7f23"
down_revision: str | Sequence[str] | None = "17f4cf2162e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from manashelper.platform.i18n.seed import import_document
    from ui_flows.application.texts import validate_text_document

    document = import_document()
    if validate_text_document(document):
        raise ValueError("The source text catalog does not satisfy the publication contract")
    baseline = document.model_dump(mode="json")

    op.create_table(
        "text_catalog_releases",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("draft_revision >= 0", name="ck_text_catalog_release_revision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_revision", name="uq_text_catalog_release_revision"),
    )
    op.create_table(
        "text_catalog_state",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column("current_release", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_text_catalog_state_singleton"),
        sa.CheckConstraint("revision >= 0", name="ck_text_catalog_state_revision"),
        sa.ForeignKeyConstraint(
            ["current_release"], ["text_catalog_releases.id"], name="fk_text_catalog_current_release"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    releases = sa.table(
        "text_catalog_releases",
        sa.column("id", sa.Integer()),
        sa.column("draft_revision", sa.Integer()),
        sa.column("document", postgresql.JSONB()),
        sa.column("author_id", sa.BigInteger()),
    )
    state = sa.table(
        "text_catalog_state",
        sa.column("id", sa.Integer()),
        sa.column("revision", sa.Integer()),
        sa.column("draft", postgresql.JSONB()),
        sa.column("current_release", sa.Integer()),
    )
    op.bulk_insert(releases, [{"id": 1, "draft_revision": 0, "document": baseline, "author_id": None}])
    op.bulk_insert(state, [{"id": 1, "revision": 0, "draft": baseline, "current_release": 1}])

    op.add_column("ui_flow_versions", sa.Column("text_catalog_release", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ui_flow_text_catalog_release", "ui_flow_versions", "text_catalog_releases", ["text_catalog_release"], ["id"]
    )
    # Older application writers do not know the new nullable column. Readers
    # interpret their NULL as this same baseline; existing documents are untouched.
    op.execute(sa.text("UPDATE ui_flow_versions SET text_catalog_release = 1 WHERE text_catalog_release IS NULL"))
    op.execute(
        sa.text(
            """CREATE FUNCTION reject_text_catalog_release_change() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'Published text catalog releases are immutable';
            END;
            $$"""
        )
    )
    op.execute(
        sa.text(
            """CREATE TRIGGER text_catalog_releases_immutable
            BEFORE UPDATE OR DELETE ON text_catalog_releases
            FOR EACH ROW EXECUTE FUNCTION reject_text_catalog_release_change()"""
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_ui_flow_text_catalog_release", "ui_flow_versions", type_="foreignkey")
    op.drop_column("ui_flow_versions", "text_catalog_release")
    op.drop_table("text_catalog_state")
    op.drop_table("text_catalog_releases")
    op.execute(sa.text("DROP FUNCTION reject_text_catalog_release_change()"))
