"""add full-text search index to document_chunks

Revision ID: f4b8e2a91d67
Revises: e1a7c9d4f882
Create Date: 2026-08-12 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f4b8e2a91d67'
down_revision: Union[str, Sequence[str], None] = 'e1a7c9d4f882'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # STORED generated column — Postgres (re)computes and persists this on
    # every insert/update of `content`, so keyword search never reads a
    # stale tsvector.
    op.execute(
        "ALTER TABLE document_chunks "
        "ADD COLUMN IF NOT EXISTS content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_content_tsv "
        "ON document_chunks USING gin(content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_content_tsv")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv")