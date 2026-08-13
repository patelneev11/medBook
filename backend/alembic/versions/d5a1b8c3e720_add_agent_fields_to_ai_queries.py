"""add agent conversation threading and tool-call metadata to ai_queries

Revision ID: d5a1b8c3e720
Revises: c2d7f9a1e356
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd5a1b8c3e720'
down_revision: Union[str, Sequence[str], None] = 'c2d7f9a1e356'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # gen_random_uuid() is built into PostgreSQL 13+ (no pgcrypto needed) and
    # gives pre-existing rows their own single-message conversation, so the
    # column can be NOT NULL from the start.
    op.add_column(
        "ai_queries",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_index("ix_ai_queries_conversation_id", "ai_queries", ["conversation_id"])
    # Threads are always read in order — the composite index is what the
    # history load actually uses.
    op.create_index(
        "ix_ai_queries_conversation_created",
        "ai_queries",
        ["conversation_id", "created_at"],
    )

    op.add_column("ai_queries", sa.Column("tool_calls", sa.JSON(), nullable=True))
    op.add_column("ai_queries", sa.Column("documents_accessed", sa.JSON(), nullable=True))
    op.add_column("ai_queries", sa.Column("iterations", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_queries", "iterations")
    op.drop_column("ai_queries", "documents_accessed")
    op.drop_column("ai_queries", "tool_calls")
    op.drop_index("ix_ai_queries_conversation_created", table_name="ai_queries")
    op.drop_index("ix_ai_queries_conversation_id", table_name="ai_queries")
    op.drop_column("ai_queries", "conversation_id")
