"""add search_history table

Revision ID: a3f6c8e1b204
Revises: f4b8e2a91d67
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3f6c8e1b204'
down_revision: Union[str, Sequence[str], None] = 'f4b8e2a91d67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: created manually below via .create(checkfirst=True) —
# without this, create_table's own column DDL tries to create the type a
# second time and fails with "already exists".
_search_type = postgresql.ENUM("semantic", "keyword", "hybrid", name="searchtype", create_type=False)


def upgrade() -> None:
    _search_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "search_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("search_type", _search_type, nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_history_user_id", "search_history", ["user_id"])
    op.create_index("ix_search_history_created_at", "search_history", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_search_history_created_at", table_name="search_history")
    op.drop_index("ix_search_history_user_id", table_name="search_history")
    op.drop_table("search_history")
    _search_type.drop(op.get_bind(), checkfirst=True)