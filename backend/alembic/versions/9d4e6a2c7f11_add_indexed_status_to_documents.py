"""add 'indexed' value to documentstatus enum

Revision ID: 9d4e6a2c7f11
Revises: 7c2f4b1a9e33
Create Date: 2026-08-12 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '9d4e6a2c7f11'
down_revision: Union[str, Sequence[str], None] = '7c2f4b1a9e33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'indexed'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums — downgrading would require
    # rebuilding the type. Not needed for a purely additive status value.
    pass