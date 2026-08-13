"""add embedding_costs, search_logs, and ai_queries rating/search_log link

Revision ID: c2d7f9a1e356
Revises: a3f6c8e1b204
Create Date: 2026-08-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2d7f9a1e356'
down_revision: Union[str, Sequence[str], None] = 'a3f6c8e1b204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Already created by a3f6c8e1b204 (add_search_history) — reused as-is here,
# so create_type=False.
_search_type = postgresql.ENUM("semantic", "keyword", "hybrid", name="searchtype", create_type=False)


def upgrade() -> None:
    op.create_table(
        "embedding_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_embedding_costs_document_id", "embedding_costs", ["document_id"])
    op.create_index("ix_embedding_costs_user_id", "embedding_costs", ["user_id"])
    op.create_index("ix_embedding_costs_created_at", "embedding_costs", ["created_at"])

    op.create_table(
        "search_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("search_type", _search_type, nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("search_time_ms", sa.Integer(), nullable=False),
        sa.Column("had_results", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_logs_user_id", "search_logs", ["user_id"])
    op.create_index("ix_search_logs_created_at", "search_logs", ["created_at"])

    op.add_column(
        "ai_queries",
        sa.Column("search_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("search_logs.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("ai_queries", sa.Column("helpful", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_queries", "helpful")
    op.drop_column("ai_queries", "search_log_id")

    op.drop_index("ix_search_logs_created_at", table_name="search_logs")
    op.drop_index("ix_search_logs_user_id", table_name="search_logs")
    op.drop_table("search_logs")

    op.drop_index("ix_embedding_costs_created_at", table_name="embedding_costs")
    op.drop_index("ix_embedding_costs_user_id", table_name="embedding_costs")
    op.drop_index("ix_embedding_costs_document_id", table_name="embedding_costs")
    op.drop_table("embedding_costs")