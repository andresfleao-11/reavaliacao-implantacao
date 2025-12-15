"""add failure_reason to quote_sources

Revision ID: 017
Revises: 016
Create Date: 2024-12-15 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '017'
down_revision: Union[str, None] = '016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add failure_reason column to quote_sources table
    op.add_column(
        'quote_sources',
        sa.Column('failure_reason', sa.String(50), nullable=True)
    )


def downgrade() -> None:
    # Remove failure_reason column from quote_sources table
    op.drop_column('quote_sources', 'failure_reason')
