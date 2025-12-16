"""add quote_source_failures table

Revision ID: 020
Revises: 019
Create Date: 2024-12-16 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '020'
down_revision: Union[str, None] = '019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create quote_source_failures table
    op.create_table(
        'quote_source_failures',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('quote_request_id', sa.Integer(), sa.ForeignKey('quote_requests.id'), nullable=False, index=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=True, index=True),
        sa.Column('product_title', sa.Text(), nullable=True),
        sa.Column('google_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('extracted_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('failure_reason', sa.String(50), nullable=False, server_default='OTHER'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('quote_source_failures')
