"""add_embeddings_to_chunks

Revision ID: e1a7c9d4f882
Revises: 9d4e6a2c7f11
Create Date: 2026-08-12 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a7c9d4f882'
down_revision: Union[str, Sequence[str], None] = '9d4e6a2c7f11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # document_chunks.embedding is already vector(384) (migrated in an
    # earlier Session 6 migration when the project switched to local
    # sentence-transformers embeddings instead of a 1536-dim hosted model)
    # — nothing to change on the column itself here.

    # Approximate similarity search index. lists=100 is a reasonable
    # starting point for a small/dev-sized corpus; IVFFLAT recall improves
    # after a REINDEX once there's substantially more data to cluster.
    op.create_index(
        'idx_chunks_embedding_ivfflat',
        'document_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='ivfflat',
        postgresql_with={'lists': '100'},
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )

    # document_id already has ix_document_chunks_document_id from the
    # initial schema migration — a second single-column index on the same
    # column would be a pure duplicate (extra disk, extra write cost, no
    # query benefit), so it's intentionally not recreated here.

    op.create_index(
        'idx_chunks_document_id_chunk_index',
        'document_chunks',
        ['document_id', 'chunk_index'],
    )

    op.add_column('document_chunks', sa.Column('embedding_model', sa.String(length=100), nullable=True))
    op.add_column('document_chunks', sa.Column('embedding_generated_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        'documents',
        sa.Column('embedding_status', sa.String(length=20), nullable=False, server_default='pending'),
    )


def downgrade() -> None:
    op.drop_column('documents', 'embedding_status')
    op.drop_column('document_chunks', 'embedding_generated_at')
    op.drop_column('document_chunks', 'embedding_model')
    op.drop_index('idx_chunks_document_id_chunk_index', table_name='document_chunks')
    op.drop_index('idx_chunks_embedding_ivfflat', table_name='document_chunks')