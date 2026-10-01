from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "affiliate_documents",
        sa.Column("affiliate_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_affiliate_documents_affiliate_id_affiliates",
        "affiliate_documents",
        "affiliates",
        ["affiliate_id"],
        ["id"],
    )
    op.create_index(
        "ix_affiliate_documents_affiliate_id",
        "affiliate_documents",
        ["affiliate_id"],
    )
    op.create_table(
        "affiliate_document_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('approved', 'rejected')",
            name="ck_affiliate_document_reviews_status",
        ),
        sa.CheckConstraint(
            "status != 'rejected' OR "
            "(rejection_reason IS NOT NULL AND length(trim(rejection_reason)) > 0)",
            name="ck_affiliate_document_reviews_rejection_reason",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["affiliate_documents.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["tenant_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_affiliate_document_reviews_document_id",
        "affiliate_document_reviews",
        ["document_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM affiliate_documents WHERE affiliate_id IS NOT NULL LIMIT 1")
    ).first():
        raise RuntimeError(
            "Cannot downgrade affiliate document reviews while merchant-scoped documents exist"
        )
    if bind.execute(sa.text("SELECT 1 FROM affiliate_document_reviews LIMIT 1")).first():
        raise RuntimeError(
            "Cannot downgrade affiliate document reviews while review history exists"
        )

    op.drop_index(
        "ix_affiliate_document_reviews_document_id",
        table_name="affiliate_document_reviews",
    )
    op.drop_table("affiliate_document_reviews")
    op.drop_index("ix_affiliate_documents_affiliate_id", table_name="affiliate_documents")
    op.drop_constraint(
        "fk_affiliate_documents_affiliate_id_affiliates",
        "affiliate_documents",
        type_="foreignkey",
    )
    op.drop_column("affiliate_documents", "affiliate_id")
