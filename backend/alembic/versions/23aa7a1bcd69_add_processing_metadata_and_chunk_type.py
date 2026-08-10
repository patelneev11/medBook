"""add processing metadata to documents and chunk_type to document_chunks

Revision ID: 23aa7a1bcd69
Revises: b9e1f2a3c4d5
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '23aa7a1bcd69'
down_revision: Union[str, Sequence[str], None] = 'b9e1f2a3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


chunk_type_enum = sa.Enum('paragraph', 'table', 'list', 'header+content', name='chunktype')


def upgrade() -> None:
    op.add_column('documents', sa.Column('chunk_count', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documents', sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True))

    chunk_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('document_chunks', sa.Column('chunk_type', chunk_type_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('document_chunks', 'chunk_type')
    chunk_type_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_column('documents', 'processing_completed_at')
    op.drop_column('documents', 'processing_started_at')
    op.drop_column('documents', 'error_message')
    op.drop_column('documents', 'chunk_count')