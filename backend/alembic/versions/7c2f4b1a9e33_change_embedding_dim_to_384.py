"""change embedding column to vector(384) for local MiniLM embeddings

Revision ID: 7c2f4b1a9e33
Revises: 36e8d9ad6a73
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = '7c2f4b1a9e33'
down_revision: Union[str, Sequence[str], None] = '36e8d9ad6a73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # embedding is NULL on every existing row (Session 6 hasn't generated
    # any yet), so there's no data to reconcile across the dimension change.
    op.alter_column('document_chunks', 'embedding', type_=Vector(384))


def downgrade() -> None:
    op.alter_column('document_chunks', 'embedding', type_=Vector(1536))