"""add screenshot to vehicle_price_bank

Revision ID: 021
Revises: 020
Create Date: 2024-12-16 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add screenshot columns to vehicle_price_bank
    op.add_column('vehicle_price_bank', sa.Column('screenshot_file_id', sa.Integer(), sa.ForeignKey('files.id'), nullable=True))
    op.add_column('vehicle_price_bank', sa.Column('screenshot_path', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('vehicle_price_bank', 'screenshot_path')
    op.drop_column('vehicle_price_bank', 'screenshot_file_id')
