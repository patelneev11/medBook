"""add display_name to documents

Revision ID: b9e1f2a3c4d5
Revises: 6fc55fc84e13
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9e1f2a3c4d5'
down_revision: Union[str, Sequence[str], None] = '6fc55fc84e13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('display_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'display_name')
